"""
core/management/commands/cleanup_stale_tasks.py
v3.67.0 — Одноразовая очистка «зависших» автозадач

Запуск:
    python manage.py cleanup_stale_tasks --dry-run   # показать без изменений
    python manage.py cleanup_stale_tasks              # выполнить

Что делает:
- Закрывает TESTING задачи, если образец уже IN_TESTING или дальше
- Закрывает MANUFACTURING задачи, если образец уже не в MANUFACTURING
- Закрывает ACCEPT_FROM_UZK задачи, если образец уже не в UZK_TESTING/UZK_READY
- Закрывает VERIFY_REGISTRATION задачи, если образец уже не PENDING_VERIFICATION
- Закрывает ACCEPT_SAMPLE задачи, если образец уже принят
"""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)

# Статусы, при которых задача данного типа уже не нужна
STALE_RULES = {
    'TESTING': {
        # Если образец уже испытывается или дальше — задача не нужна
        'close_if_status_in': (
            'IN_TESTING', 'TESTED', 'DRAFT_READY', 'PROTOCOL_READY',
            'COMPLETED', 'CANCELLED',
        ),
    },
    'MANUFACTURING': {
        # Если образец уже не в мастерской — задача не нужна
        'close_if_status_not_in': ('MANUFACTURING',),
    },
    'ACCEPT_FROM_UZK': {
        # Если образец уже не в УЗК — задача не нужна
        'close_if_status_not_in': ('UZK_TESTING', 'UZK_READY'),
    },
    'VERIFY_REGISTRATION': {
        'close_if_status_not_in': ('PENDING_VERIFICATION',),
    },
    'ACCEPT_SAMPLE': {
        'close_if_status_not_in': ('MANUFACTURED',),
    },
}


class Command(BaseCommand):
    help = 'Закрывает устаревшие автозадачи, если образец уже прошёл соответствующий этап'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать, какие задачи будут закрыты, но не закрывать',
        )

    def handle(self, *args, **options):
        from core.models.tasks import Task
        from core.models.sample import Sample

        dry_run = options['dry_run']
        now = timezone.now()
        total_closed = 0

        # Все открытые автозадачи, привязанные к образцам
        open_tasks = Task.objects.filter(
            entity_type='sample',
            entity_id__isnull=False,
            status__in=('OPEN', 'IN_PROGRESS'),
            task_type__in=STALE_RULES.keys(),
        ).order_by('task_type', 'entity_id')

        # Собираем все нужные sample_id
        sample_ids = set(open_tasks.values_list('entity_id', flat=True))
        samples = {
            s.id: s for s in
            Sample.objects.filter(id__in=sample_ids).only('id', 'status', 'cipher')
        }

        for task_type, rule in STALE_RULES.items():
            tasks = open_tasks.filter(task_type=task_type)
            closed_count = 0

            for task in tasks:
                sample = samples.get(task.entity_id)
                if not sample:
                    # Образец удалён — задачу закрываем
                    should_close = True
                    reason = 'образец не найден'
                elif 'close_if_status_in' in rule:
                    should_close = sample.status in rule['close_if_status_in']
                    reason = f'образец в статусе {sample.status}'
                elif 'close_if_status_not_in' in rule:
                    should_close = sample.status not in rule['close_if_status_not_in']
                    reason = f'образец в статусе {sample.status}'
                else:
                    should_close = False
                    reason = ''

                if should_close:
                    cipher = sample.cipher if sample else f'#{task.entity_id}'
                    if dry_run:
                        self.stdout.write(
                            f'  [DRY-RUN] {task_type}: {cipher} — {reason}'
                        )
                    else:
                        task.status = 'DONE'
                        task.completed_at = now
                        task.save(update_fields=['status', 'completed_at'])
                    closed_count += 1

            if closed_count:
                prefix = '[DRY-RUN] ' if dry_run else ''
                self.stdout.write(f'{prefix}{task_type}: закрыто {closed_count} задач')
            total_closed += closed_count

        self.stdout.write(
            f'\n{"[DRY-RUN] " if dry_run else ""}Итого закрыто: {total_closed} задач'
        )
