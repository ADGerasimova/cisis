"""
core/management/commands/create_testing_tasks.py
v3.67.0 — Создание задач TESTING за 2 дня до дедлайна

Запуск:
    python manage.py create_testing_tasks

Cron (каждый день в 08:00 MSK):
    0 8 * * * cd /opt/cisis && docker compose exec -T web python manage.py create_testing_tasks >> /var/log/cisis/testing_tasks.log 2>&1

Логика:
- Находит образцы, у которых дедлайн через ≤2 дня (или уже просрочен)
- Образец должен быть в статусе ожидания испытания (REGISTERED, ACCEPTED_IN_LAB и т.д.)
- Испытание ещё не начато (не IN_TESTING и далее)
- Открытая задача TESTING по этому образцу ещё не существует
- Создаёт задачу TESTING всем сотрудникам целевой лаборатории
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


# Статусы, при которых испытание ещё НЕ начато, но образец готов
AWAITING_TEST_STATUSES = (
    'REGISTERED',
    'ACCEPTED_IN_LAB',
    'TRANSFERRED',
    'CONDITIONING',
    'READY_FOR_TEST',
)

# За сколько дней до дедлайна создавать задачу
DAYS_BEFORE_DEADLINE = 2


class Command(BaseCommand):
    help = 'Создаёт задачи TESTING для образцов, у которых дедлайн через ≤2 дня и испытание не начато'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, какие задачи будут созданы, но не создавать',
        )
        parser.add_argument(
            '--days',
            type=int,
            default=DAYS_BEFORE_DEADLINE,
            help=f'За сколько дней до дедлайна создавать задачу (по умолчанию {DAYS_BEFORE_DEADLINE})',
        )

    def handle(self, *args, **options):
        from core.models.sample import Sample
        from core.models.tasks import Task
        from core.models import User
        from core.views.task_views import create_auto_task

        dry_run = options['dry_run']
        days = options['days']
        today = timezone.now().date()
        threshold_date = today + timedelta(days=days)

        # Образцы: ожидают испытания, дедлайн ≤ threshold, есть лаборатория
        samples = Sample.objects.filter(
            status__in=AWAITING_TEST_STATUSES,
            deadline__isnull=False,
            deadline__lte=threshold_date,
            laboratory_id__isnull=False,
        ).select_related('laboratory')

        # Исключаем те, по которым уже есть открытая задача TESTING
        existing_task_sample_ids = set(
            Task.objects.filter(
                task_type='TESTING',
                entity_type='sample',
                status__in=('OPEN', 'IN_PROGRESS'),
            ).values_list('entity_id', flat=True)
        )

        created_count = 0
        skipped_count = 0

        for sample in samples:
            if sample.id in existing_task_sample_ids:
                skipped_count += 1
                continue

            # Сотрудники целевой лаборатории
            lab_user_ids = list(
                User.objects.filter(
                    laboratory_id=sample.laboratory_id,
                    is_active=True,
                ).values_list('id', flat=True)
            )

            if not lab_user_ids:
                self.stdout.write(
                    f'  ⚠ {sample.cipher}: нет сотрудников в лаборатории '
                    f'{sample.laboratory.name if sample.laboratory else "?"}'
                )
                continue

            days_left = (sample.deadline - today).days
            if days_left < 0:
                urgency = f'ПРОСРОЧЕН на {abs(days_left)} дн.'
            elif days_left == 0:
                urgency = 'СЕГОДНЯ'
            elif days_left == 1:
                urgency = 'ЗАВТРА'
            else:
                urgency = f'через {days_left} дн.'

            if dry_run:
                self.stdout.write(
                    f'  [DRY-RUN] {sample.cipher} — дедлайн {urgency}, '
                    f'{len(lab_user_ids)} исполнит.'
                )
            else:
                try:
                    create_auto_task('TESTING', sample, lab_user_ids, created_by=None)
                    created_count += 1
                    self.stdout.write(
                        f'  ✓ {sample.cipher} — дедлайн {urgency}, '
                        f'{len(lab_user_ids)} исполнит.'
                    )
                except Exception:
                    logger.exception(f'Ошибка создания задачи TESTING для {sample.cipher}')
                    self.stdout.write(f'  ✗ {sample.cipher} — ошибка!')

        # Итог
        prefix = '[DRY-RUN] ' if dry_run else ''
        self.stdout.write(
            f'\n{prefix}Итого: создано {created_count}, '
            f'пропущено {skipped_count} (задача уже есть), '
            f'всего кандидатов {samples.count()}'
        )
