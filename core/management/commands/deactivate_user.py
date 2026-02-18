# core/management/commands/deactivate_user.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import User, Laboratory, Equipment


class Command(BaseCommand):
    help = 'Деактивировать пользователя и передать его обязанности'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Username пользователя')
        parser.add_argument('--reason', type=str, default='', help='Причина увольнения')
        parser.add_argument(
            '--transfer-to',
            type=str,
            help='Username для передачи обязанностей (для заведующих и ответственных)'
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options['username'])
        except User.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f'❌ Пользователь {options["username"]} не найден')
            )
            return

        # Проверяем, активен ли пользователь
        if not user.is_active:
            self.stdout.write(
                self.style.WARNING(f'⚠ Пользователь {user.full_name} уже деактивирован')
            )
            return

        # Показываем информацию
        self.stdout.write(f'\n🔍 Деактивация пользователя:')
        self.stdout.write(f'   ФИО: {user.full_name}')
        self.stdout.write(f'   Роль: {user.get_role_display()}')
        lab = user.laboratory.code_display if user.laboratory else 'Нет'
        self.stdout.write(f'   Лаборатория: {lab}')

        # Проверяем обязанности
        headed_labs = Laboratory.objects.filter(head=user)
        responsible_equipment = Equipment.objects.filter(responsible_person=user)

        if headed_labs.exists() or responsible_equipment.exists():
            self.stdout.write(f'\n⚠ Обнаружены обязанности:')

            if headed_labs.exists():
                for lab in headed_labs:
                    self.stdout.write(f'   • Заведующий лабораторией: {lab.code_display}')

            if responsible_equipment.exists():
                self.stdout.write(f'   • Ответственный за оборудование: {responsible_equipment.count()} ед.')

            if not options['transfer_to']:
                self.stdout.write(
                    self.style.ERROR(
                        '\n❌ Необходимо указать --transfer-to для передачи обязанностей'
                    )
                )
                return

            # Передаём обязанности
            try:
                new_user = User.objects.get(username=options['transfer_to'])
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f'❌ Пользователь {options["transfer_to"]} не найден'
                    )
                )
                return

            self.stdout.write(f'\n📝 Передача обязанностей → {new_user.full_name}')

            # Передаём лаборатории
            for lab in headed_labs:
                lab.head = new_user
                lab.save()
                self.stdout.write(f'   ✓ Лаборатория {lab.code_display}')

            # Передаём оборудование
            count = responsible_equipment.update(responsible_person=new_user)
            if count > 0:
                self.stdout.write(f'   ✓ Оборудование: {count} ед.')

        # Деактивируем
        user.is_active = False
        if hasattr(user, 'termination_date'):
            user.termination_date = timezone.now().date()
        if hasattr(user, 'termination_reason') and options['reason']:
            user.termination_reason = options['reason']
        user.save()

        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Пользователь {user.full_name} успешно деактивирован'
            )
        )