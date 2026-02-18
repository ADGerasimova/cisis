"""
Модель пользователя и связанные классы
"""

from django.db import models


# =============================================================================
# РОЛИ ПОЛЬЗОВАТЕЛЕЙ
# =============================================================================

class UserRole(models.TextChoices):
    # Руководство
    CEO = 'CEO', 'Генеральный директор'
    CTO = 'CTO', 'Технический директор'
    SYSADMIN = 'SYSADMIN', 'Системный администратор'

    # Лаборатории
    LAB_HEAD = 'LAB_HEAD', 'Заведующий лабораторией'
    TESTER = 'TESTER', 'Испытатель'

    # Отдел по работе с заказчиками (регистрация образцов)
    CLIENT_DEPT_HEAD = 'CLIENT_DEPT_HEAD', 'Руководитель отдела по работе с заказчиками'
    CLIENT_MANAGER = 'CLIENT_MANAGER', 'Специалист по работе с заказчиками'
    CONTRACT_SPEC = 'CONTRACT_SPEC', 'Специалист по договорам'

    # СМК (проверка протоколов)
    QMS_HEAD = 'QMS_HEAD', 'Руководитель СМК'
    QMS_ADMIN = 'QMS_ADMIN', 'Администратор СМК'
    METROLOGIST = 'METROLOGIST', 'Метролог'

    # Мастерская (относится к лаборатории МИ)
    WORKSHOP = 'WORKSHOP', 'Сотрудник мастерской'

    # Бухгалтерия
    ACCOUNTANT = 'ACCOUNTANT', 'Бухгалтер'

    # Прочие
    OTHER = 'OTHER', 'Прочий'


# =============================================================================
# МЕНЕДЖЕР МОДЕЛИ USER
# =============================================================================

class UserManager(models.Manager):
    def get_by_natural_key(self, username):
        return self.get(username=username)


# =============================================================================
# МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ
# =============================================================================
# Собственная модель пользователя — НЕ наследуем от AbstractUser,
# потому что таблица users уже существует со своей схемой.
# Для аутентификации через Django используем custom backend.
# =============================================================================

class User(models.Model):
    username       = models.CharField(max_length=100, unique=True)
    password_hash  = models.CharField(max_length=255)
    email          = models.CharField(max_length=255, default='', blank=True)
    first_name     = models.CharField(max_length=100, default='', blank=True)
    last_name      = models.CharField(max_length=100, default='', blank=True)
    role           = models.CharField(max_length=20, default=UserRole.OTHER, choices=UserRole.choices)
    laboratory     = models.ForeignKey(
        'Laboratory',  # Ссылка на модель Laboratory из того же приложения
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    is_active      = models.BooleanField(default=True)
    is_staff       = models.BooleanField(default=False)
    is_superuser   = models.BooleanField(default=False)
    ui_preferences = models.JSONField(default=dict, blank=True)
    last_login     = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    objects = UserManager()

    # Обязательные атрибуты для Django auth
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        db_table = 'users'
        managed  = False
        ordering = ['last_name', 'first_name']
        verbose_name        = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f'{self.last_name} {self.first_name} ({self.username})'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    # ═══════════════════════════════════════════════════════════════
    # МЕТОДЫ ДЛЯ РАБОТЫ С ПАРОЛЯМИ
    # ═══════════════════════════════════════════════════════════════

    def check_password(self, raw_password):
        """Проверяет соответствие пароля хэшу"""
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password_hash)

    def set_password(self, raw_password):
        """Устанавливает новый пароль"""
        from django.contrib.auth.hashers import make_password
        self.password_hash = make_password(raw_password)

    # ═══════════════════════════════════════════════════════════════
    # ИНТЕРФЕЙС ДЛЯ DJANGO AUTH BACKEND
    # ═══════════════════════════════════════════════════════════════

    @property
    def is_authenticated(self):
        """Django ожидает этот атрибут у объекта user"""
        return True

    @property
    def is_anonymous(self):
        """Django ожидает этот атрибут у объекта user"""
        return False

    def has_perm(self, perm, obj=None):
        """Проверка прав. SYSADMIN и суперпользователи имеют все права."""
        if self.is_superuser or self.role == UserRole.SYSADMIN:
            return True

        # Для остальных — базовый доступ если is_staff
        return self.is_active and self.is_staff

    def has_module_perms(self, app_label):
        """Проверка прав к приложению."""
        if self.is_superuser or self.role == UserRole.SYSADMIN:
            return True

        # В Django Admin могут заходить только административные роли
        allowed_roles = ['SYSADMIN', 'QMS_HEAD', 'LAB_HEAD']
        if self.role in allowed_roles and self.is_active and self.is_staff:
            return True

        # Остальные роли не имеют доступа ни к каким модулям админки
        return False

    # ═══════════════════════════════════════════════════════════════
    # ЗАЩИТА ОТ УДАЛЕНИЯ
    # ═══════════════════════════════════════════════════════════════

    def delete(self, *args, **kwargs):
        """
        БЛОКИРУЕМ удаление пользователей!
        Вместо удаления используйте деактивацию.
        """
        raise PermissionError(
            f'Удаление пользователей запрещено! '
            f'Используйте деактивацию: user.is_active = False'
        )

    def deactivate(self, reason=''):
        """
        Безопасная деактивация вместо удаления
        """
        from django.utils import timezone

        self.is_active = False
        if hasattr(self, 'termination_date'):
            self.termination_date = timezone.now().date()
        if hasattr(self, 'termination_reason'):
            self.termination_reason = reason
        self.save()

        return f'Пользователь {self.full_name} деактивирован'
