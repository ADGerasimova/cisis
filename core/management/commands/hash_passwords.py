"""
Django management command: хеширование plain-text паролей.

Использование:
    python manage.py hash_passwords
    python manage.py hash_passwords --dry-run

Проходит по всем пользователям, чей password_hash не начинается
с 'pbkdf2_sha256$' (т.е. ещё не захеширован Django), и хеширует
текущее значение через make_password().

Безопасно запускать многократно — уже захешированные пароли пропускаются.

Размещение: core/management/commands/hash_passwords.py
(создать папки management/ и commands/ с __init__.py если их нет)
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from core.models import User


class Command(BaseCommand):
    help = 'Хеширование plain-text паролей пользователей через Django make_password()'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано, без изменений в БД',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        users = User.objects.all()

        hashed_count = 0
        skipped_count = 0

        for user in users:
            current_hash = user.password_hash

            # Пропускаем уже захешированные
            if current_hash and current_hash.startswith(('pbkdf2_sha256$', 'argon2', 'bcrypt')):
                skipped_count += 1
                continue

            if not current_hash or current_hash.strip() == '':
                self.stdout.write(
                    self.style.WARNING(
                        f'  ПРОПУСК {user.username}: пустой пароль'
                    )
                )
                skipped_count += 1
                continue

            if dry_run:
                self.stdout.write(
                    f'  [DRY RUN] {user.username}: будет захеширован'
                )
            else:
                user.password_hash = make_password(current_hash)
                user.save(update_fields=['password_hash'])
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  OK {user.username}'
                    )
                )

            hashed_count += 1

        self.stdout.write('')
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN: {hashed_count} будет захешировано, '
                    f'{skipped_count} пропущено'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Готово: {hashed_count} захешировано, '
                    f'{skipped_count} пропущено'
                )
            )
