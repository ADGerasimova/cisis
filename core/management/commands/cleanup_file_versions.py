"""
cleanup_file_versions — чистит исторические версии файлов (current_version=False).

Контекст (v3.89.0):
    20.04.2026 пользователь Жулькина А.Л. (id=22) при массовой загрузке
    личной папки с ~1860 CSV-файлами породила ~28000 версий в S3
    из-за автоверсионности по original_name. Контент во всех версиях
    идентичен (distinct file_size = 1 в каждой группе) — это не история
    правок, а повторные аплоады одного и того же файла.

    Автоверсионность для PERSONAL в v3.89.0 отключена; эта команда
    разбирает уже накопленный мусор.

Использование:
    # Сначала dry-run чтобы посмотреть, что будет удалено:
    python manage.py cleanup_file_versions --category=PERSONAL --dry-run

    # Если цифры устраивают — реальный прогон:
    python manage.py cleanup_file_versions --category=PERSONAL

    # Только для конкретного пользователя (безопаснее первая итерация):
    python manage.py cleanup_file_versions --category=PERSONAL --owner-id=22 --dry-run

Логика безопасности:
    По умолчанию команда удаляет только версии, у которых в группе
    (entity/owner/folder, original_name) все записи имеют одинаковый
    file_size — это сильный прокси того, что контент идентичен и
    версионирование было ложным. Для версий с разными размерами
    пропускается (требуется --include-size-mismatch).

    Режим --aggressive дополнительно удаляет версии с разными размерами
    старше --keep-days (по умолчанию 90). Использовать только после
    ручного просмотра топ-групп.
"""

import logging
from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models.files import File

logger = logging.getLogger(__name__)


BATCH_DELETE_SIZE = 900  # S3 DeleteObjects лимит 1000, оставляем запас


class Command(BaseCommand):
    help = 'Чистит исторические версии файлов (current_version=False) от дубликатов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--category',
            choices=['PERSONAL', 'INBOX', 'QMS', 'SAMPLE',
                     'CLIENT', 'CONTRACT', 'EQUIPMENT', 'STANDARD', 'SPECIFICATION'],
            help='Ограничить категорией (по умолчанию — все)',
        )
        parser.add_argument(
            '--owner-id', type=int,
            help='Ограничить конкретным пользователем (owner_id). '
                 'Работает только вместе с --category=PERSONAL.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Ничего не удалять, только показать статистику',
        )
        parser.add_argument(
            '--include-size-mismatch', action='store_true',
            help='Удалять и версии с разными размерами (по умолчанию '
                 'удаляются только группы с одинаковым file_size)',
        )
        parser.add_argument(
            '--aggressive', action='store_true',
            help='В сочетании с --include-size-mismatch: удалять версии '
                 'старше --keep-days даже при разных размерах',
        )
        parser.add_argument(
            '--keep-days', type=int, default=90,
            help='При --aggressive: оставлять версии младше N дней (default: 90)',
        )
        parser.add_argument(
            '--limit', type=int,
            help='Ограничить число групп для обработки (для тестирования)',
        )

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        category = opts['category']
        owner_id = opts['owner_id']
        include_size_mismatch = opts['include_size_mismatch']
        aggressive = opts['aggressive']
        keep_days = opts['keep_days']
        limit = opts['limit']

        if aggressive and not include_size_mismatch:
            raise CommandError('--aggressive требует --include-size-mismatch')
        if owner_id and category != 'PERSONAL':
            raise CommandError('--owner-id имеет смысл только с --category=PERSONAL')

        mode = 'DRY-RUN' if dry else 'LIVE'
        self.stdout.write(self.style.WARNING(f'[{mode}] cleanup_file_versions'))
        self.stdout.write(f'  category            = {category or "все"}')
        self.stdout.write(f'  owner_id            = {owner_id or "все"}')
        self.stdout.write(f'  include size diff   = {include_size_mismatch}')
        self.stdout.write(f'  aggressive          = {aggressive}')
        if aggressive:
            self.stdout.write(f'  keep_days           = {keep_days}')
        self.stdout.write('')

        # ─── Строим группы (entity, original_name) → [non-current-версии] ───
        qs = File.objects.filter(
            current_version=False,
            is_deleted=False,
        )
        if category:
            qs = qs.filter(category=category)
        if owner_id:
            qs = qs.filter(owner_id=owner_id)

        # Ключ группы: всё, что идентифицирует «один логический файл».
        # Для PERSONAL: owner_id + personal_folder_id + original_name
        # Для SAMPLE:   sample_id + original_name
        # и т.д.
        groups = defaultdict(list)
        for f in qs.iterator(chunk_size=2000):
            key = (
                f.category,
                f.sample_id, f.acceptance_act_id, f.contract_id,
                f.equipment_id, f.standard_id, f.specification_id,
                f.owner_id, f.personal_folder_id,
                f.original_name,
            )
            groups[key].append(f)

        total_groups = len(groups)
        self.stdout.write(f'Найдено групп с не-current версиями: {total_groups}')

        if limit:
            groups = dict(list(groups.items())[:limit])
            self.stdout.write(f'Обрабатываем первые {len(groups)} групп (--limit)')

        # ─── Отбор кандидатов на удаление ───
        to_delete = []  # список File объектов
        skipped_size_diff = 0
        cutoff = timezone.now() - timedelta(days=keep_days)

        for key, versions in groups.items():
            sizes = {v.file_size for v in versions}
            size_consistent = len(sizes) == 1

            if size_consistent:
                to_delete.extend(versions)
            elif include_size_mismatch:
                if aggressive:
                    # Только те, что старше cutoff
                    for v in versions:
                        if v.uploaded_at < cutoff:
                            to_delete.append(v)
                else:
                    to_delete.extend(versions)
            else:
                skipped_size_diff += len(versions)

        total_bytes = sum(v.file_size for v in to_delete)
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'К удалению: {len(to_delete)} записей, '
            f'{total_bytes / 1024 / 1024:.1f} МБ'
        ))
        if skipped_size_diff:
            self.stdout.write(self.style.WARNING(
                f'Пропущено из-за разных размеров: {skipped_size_diff} '
                f'(используйте --include-size-mismatch для удаления)'
            ))

        if dry or not to_delete:
            self.stdout.write('')
            self.stdout.write(self.style.NOTICE(
                'DRY-RUN: ничего не удалено. Для реального прогона '
                'запустите без --dry-run.'
            ))
            return

        # ─── Удаление: S3 + БД ───
        self.stdout.write('')
        self.stdout.write('Удаляю...')

        from core.services.s3_utils import _get_client, get_bucket, is_s3_enabled

        s3_enabled = is_s3_enabled()
        s3_client = _get_client() if s3_enabled else None
        bucket = get_bucket() if s3_enabled else None

        deleted_s3 = 0
        failed_s3 = 0

        # S3 batch delete
        if s3_enabled:
            keys = [v.file_path for v in to_delete if v.file_path]
            for i in range(0, len(keys), BATCH_DELETE_SIZE):
                batch = keys[i:i + BATCH_DELETE_SIZE]
                try:
                    resp = s3_client.delete_objects(
                        Bucket=bucket,
                        Delete={
                            'Objects': [{'Key': k} for k in batch],
                            'Quiet': True,
                        },
                    )
                    errors = resp.get('Errors', [])
                    failed_s3 += len(errors)
                    deleted_s3 += len(batch) - len(errors)
                    if errors:
                        for err in errors[:5]:
                            self.stdout.write(self.style.ERROR(
                                f'  S3 ошибка: {err.get("Key")} — {err.get("Message")}'
                            ))
                    self.stdout.write(
                        f'  S3 batch {i // BATCH_DELETE_SIZE + 1}: '
                        f'удалено {len(batch) - len(errors)}/{len(batch)}'
                    )
                except Exception as e:
                    logger.exception(f'S3 batch delete failed: {e}')
                    failed_s3 += len(batch)

        # ─── БД: пометка is_deleted (не физическое DELETE) ───
        # Причины пометки, а не физического удаления:
        #   1. Сохраняются связи в audit_log / replaces chain.
        #   2. Возможность быстрого recovery, если оказалось что удалили
        #      лишнее (физически объект ушёл из S3, но запись позволит
        #      восстановить контекст — кто/когда/как).
        now = timezone.now()
        ids = [v.id for v in to_delete]
        with transaction.atomic():
            deleted_db = File.objects.filter(id__in=ids).update(
                is_deleted=True,
                deleted_at=now,
                # deleted_by не ставим — в команде нет user. Можно было бы
                # запрашивать --system-user-id, но сейчас оставляем NULL,
                # это явно отличает system-cleanup от ручного удаления.
            )

        # ─── Итоги ───
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Готово.\n'
            f'  S3: удалено {deleted_s3}, ошибок {failed_s3}\n'
            f'  БД: помечено is_deleted={deleted_db}'
        ))
