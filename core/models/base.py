"""
Базовые справочники и вспомогательные модели:
- Laboratory (Лаборатории)
- Client (Заказчики)
- ClientContact (Контакты заказчиков)
- Contract (Договоры)
- AccreditationArea (Области аккредитации)
- Standard (Стандарты)
- Holiday (Праздничные дни)
"""

from django.db import models
from django.core.exceptions import ValidationError
import re


# =============================================================================
# ВАЛИДАТОРЫ
# =============================================================================

def validate_latin_only(value):
    """Проверяет, что строка содержит только латиницу, цифры и допустимые символы"""
    if value and not re.match(r'^[A-Za-z0-9\-_./\s]+$', value):
        raise ValidationError('Допустимы только латинские буквы, цифры и символы: - _ . /')


# =============================================================================
# 1. ЛАБОРАТОРИИ
# =============================================================================

class DepartmentType(models.TextChoices):
    LAB = 'LAB', 'Лаборатория'
    OFFICE = 'OFFICE', 'Офисное подразделение'

class Laboratory(models.Model):
    name         = models.CharField(max_length=200, verbose_name='Название')
    code         = models.CharField(max_length=10, unique=True, verbose_name='Код (латиница)')
    code_display = models.CharField(max_length=10, verbose_name='Код (отображение)')
    is_active    = models.BooleanField(default=True, verbose_name='Активна')

    department_type = models.CharField(
        max_length=20,
        default=DepartmentType.LAB,
        choices=DepartmentType.choices,
        verbose_name='Тип подразделения'
    )

    head         = models.ForeignKey(
        'User',  # Ссылка на модель User из того же приложения
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_laboratories',
        db_column='head_id',
        verbose_name='Руководитель'
    )


    class Meta:
        db_table = 'laboratories'
        managed  = False
        ordering = ['name']
        verbose_name        = 'Лаборатория'
        verbose_name_plural = 'Лаборатории'

    def __str__(self):
        return f'{self.code_display} — {self.name}'


# =============================================================================
# 2. ЗАКАЗЧИКИ
# =============================================================================

class Client(models.Model):
    name       = models.CharField(max_length=500)
    inn        = models.CharField(max_length=12, default='', blank=True)
    address    = models.TextField(default='', blank=True)
    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'clients'
        managed  = False
        ordering = ['name']
        verbose_name        = 'Заказчик'
        verbose_name_plural = 'Заказчики'

    def __str__(self):
        return self.name


# =============================================================================
# 3. КОНТАКТЫ ЗАКАЗЧИКОВ
# =============================================================================

class ClientContact(models.Model):
    client     = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='contacts')
    full_name  = models.CharField(max_length=200)
    position   = models.CharField(max_length=200, default='', blank=True)
    phone      = models.CharField(max_length=50, default='', blank=True)
    email      = models.CharField(max_length=255, default='', blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = 'client_contacts'
        managed  = False
        verbose_name        = 'Контакт заказчика'
        verbose_name_plural = 'Контакты заказчиков'

    def __str__(self):
        return f'{self.full_name} ({self.client.name})'


# =============================================================================
# 4. ДОГОВОРЫ
# =============================================================================

class ContractStatus(models.TextChoices):
    ACTIVE     = 'ACTIVE',     'Активен'
    EXPIRED    = 'EXPIRED',    'Истёк'
    TERMINATED = 'TERMINATED', 'Расторгнут'


class Contract(models.Model):
    client   = models.ForeignKey(Client, on_delete=models.CASCADE, related_name='contracts')
    number   = models.CharField(max_length=100)
    date     = models.DateField()
    end_date = models.DateField(null=True, blank=True)  # NULL = бессрочный
    status   = models.CharField(max_length=20, default=ContractStatus.ACTIVE, choices=ContractStatus.choices)
    notes    = models.TextField(default='', blank=True)

    class Meta:
        db_table        = 'contracts'
        managed         = False
        unique_together = [('client', 'number')]
        ordering        = ['-date']
        verbose_name        = 'Договор'
        verbose_name_plural = 'Договоры'

    def __str__(self):
        return f'№ {self.number} ({self.client.name})'


# =============================================================================
# 5. ОБЛАСТИ АККРЕДИТАЦИИ
# =============================================================================

class AccreditationArea(models.Model):
    name        = models.CharField(max_length=200)
    code        = models.CharField(max_length=20, unique=True)
    description = models.TextField(default='', blank=True)
    is_active   = models.BooleanField(default=True)
    is_default  = models.BooleanField(default=False)  # TRUE только для «Вне области»

    class Meta:
        db_table = 'accreditation_areas'
        managed  = False
        ordering = ['name']
        verbose_name        = 'Область аккредитации'
        verbose_name_plural = 'Области аккредитации'

    def __str__(self):
        return self.name


# =============================================================================
# 6. СТАНДАРТЫ
# =============================================================================

class Standard(models.Model):
    code      = models.CharField(max_length=50, unique=True)   # ГОСТ 1234-56
    name      = models.CharField(max_length=500)
    test_code = models.CharField(max_length=20, default='', blank=True)   # например CAI
    test_type = models.CharField(max_length=200, default='', blank=True)  # название типа испытания
    is_active = models.BooleanField(default=True)

    # M2M со областями аккредитации через посредника
    accreditation_areas = models.ManyToManyField(
        AccreditationArea,
        through='StandardAccreditationArea',
        related_name='standards',
    )

    laboratories = models.ManyToManyField(
        Laboratory,
        through='StandardLaboratory',
        related_name='standards',
    )

    class Meta:
        db_table = 'standards'
        managed  = False
        ordering = ['code']
        verbose_name        = 'Стандарт'
        verbose_name_plural = 'Стандарты'

    def __str__(self):
        return f'{self.code} — {self.name}'


# =============================================================================
# 6a. ПОСРЕДНИК: СТАНДАРТ ↔ ОБЛАСТЬ АККРЕДИТАЦИИ
# =============================================================================

class StandardAccreditationArea(models.Model):
    standard            = models.ForeignKey(Standard, on_delete=models.CASCADE)
    accreditation_area  = models.ForeignKey(AccreditationArea, on_delete=models.CASCADE)

    class Meta:
        db_table        = 'standard_accreditation_areas'
        managed         = False
        unique_together = [('standard', 'accreditation_area')]

class StandardLaboratory(models.Model):
    """Связь стандарта с лабораторией"""
    standard   = models.ForeignKey(Standard, on_delete=models.CASCADE)
    laboratory = models.ForeignKey(Laboratory, on_delete=models.CASCADE)

    class Meta:
        db_table        = 'standard_laboratories'
        managed         = False
        unique_together = [('standard', 'laboratory')]
        verbose_name        = 'Привязка стандарта к лаборатории'
        verbose_name_plural = 'Привязки стандартов к лабораториям'

    def __str__(self):
        return f'{self.standard.code} ↔ {self.laboratory.code_display}'

# =============================================================================
# 7. ПРАЗДНИЧНЫЕ И НЕРАБОЧИЕ ДНИ
# =============================================================================

class Holiday(models.Model):
    date       = models.DateField(unique=True)
    name       = models.CharField(max_length=200)
    is_working = models.BooleanField(default=False)  # TRUE = перенесённый рабочий день

    class Meta:
        db_table = 'holidays'
        managed  = False
        ordering = ['date']
        verbose_name        = 'Праздничный день'
        verbose_name_plural = 'Праздничные дни'

    def __str__(self):
        return f'{self.date} — {self.name}'

class RoleLaboratoryAccess(models.Model):
    """
    Видимость лабораторий по ролям для каждого журнала.
    laboratory = NULL означает "все лаборатории".
    """
    role       = models.CharField(max_length=20)
    journal    = models.ForeignKey(
        'Journal', on_delete=models.CASCADE,
        related_name='laboratory_access',
    )
    laboratory = models.ForeignKey(
        Laboratory, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='role_access',
    )

    class Meta:
        db_table = 'role_laboratory_access'
        managed  = False
        verbose_name        = 'Доступ к лаборатории'
        verbose_name_plural = 'Доступ к лабораториям'

    def __str__(self):
        lab = self.laboratory.code_display if self.laboratory else 'ВСЕ'
        return f'{self.role} → {self.journal.code} → {lab}'
