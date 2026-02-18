"""
Management command для очистки устаревших пользователей.

Удаляет старых пользователей из предыдущих версий:
- admin (заменён на admin1, admin2, admin3)
- tester1 (заменён на kuznetsova)
- tester2 (заменён на sokolov)

Запуск:
    python manage.py cleanup_old_users

Опции:
    --dry-run    Показать, что будет удалено, но не удалять
    --force      Удалить без подтверждения
"""

from django.core.management.base import BaseCommand
from core.models import User


class Command(BaseCommand):
    help = 'Удаление устаревших пользователей из предыдущих версий'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет удалено, но не удалять',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Удалить без подтверждения',
        )

    def handle(self, *args, **options):
        self.stdout.write('--- Очистка устаревших пользователей ---\n')

        # Список пользователей для удаления
        old_usernames = ['admin', 'tester1', 'tester2']

        # Находим пользователей
        old_users = User.objects.filter(username__in=old_usernames)

        if not old_users.exists():
            self.stdout.write(self.style.SUCCESS('✓ Устаревших пользователей не найдено'))
            return

        # Показываем что будет удалено
        self.stdout.write('Будут удалены следующие пользователи:\n')
        for user in old_users:
            lab = user.laboratory.code_display if user.laboratory else '-'
            self.stdout.write(
                f'  • {user.username:15} | {user.full_name:25} | '
                f'{user.get_role_display():30} | Лаб: {lab}'
            )

        if options['dry_run']:
            self.stdout.write('\n' + self.style.WARNING('⚠ Режим dry-run: пользователи НЕ удалены'))
            return

        # Подтверждение
        if not options['force']:
            confirm = input('\nУдалить этих пользователей? (yes/no): ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.WARNING('Отменено'))
                return

        # Удаляем
        count = old_users.count()
        old_users.delete()

        self.stdout.write('\n' + self.style.SUCCESS(f'✓ Удалено пользователей: {count}'))