"""
Сервис для работы с параметрами испытания по ГОСТ Р 56762.

Содержит:
- константу идентификации стандарта
- функцию генерации поля test_conditions
- форму GostR56762ParamsForm для модалки
"""

import re
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from ..models import SampleGostR56762Params


# =============================================================================
# КОНСТАНТЫ
# =============================================================================

GOST_R_56762_CODE = 'ГОСТ Р 56762'
SAMPLE_TEST_CONDITIONS_MAX_LENGTH = 1000


# =============================================================================
# ИДЕНТИФИКАЦИЯ СТАНДАРТА
# =============================================================================

def is_gost_r_56762_standard(standard_or_code) -> bool:
    """
    Проверяет, что стандарт — именно ГОСТ Р 56762.
    Можно передавать:
    - объект Standard
    - строку code
    """
    code = getattr(standard_or_code, 'code', standard_or_code)
    return str(code or '').strip().upper() == GOST_R_56762_CODE.upper()


# =============================================================================
# ГЕНЕРАЦИЯ СТРОКИ test_conditions
# =============================================================================

def build_test_conditions_gost_r_56762(
    data,
    *,
    max_length=SAMPLE_TEST_CONDITIONS_MAX_LENGTH
) -> str:
    """
    Генерирует строку для Sample.test_conditions
    из данных параметров ГОСТ Р 56762.

    data может быть:
    - dict (например, form.cleaned_data)
    - объект модели SampleGostR56762Params
    """

    def get(field_name):
        if isinstance(data, dict):
            return data.get(field_name)
        return getattr(data, field_name, None)

    parts = []

    temperature_c             = get('temperature_c')
    relative_humidity_percent = get('relative_humidity_percent')
    water_exposure            = get('water_exposure')
    boiling_water_exposure    = get('boiling_water_exposure')
    other_fluid_medium        = get('other_fluid_medium')
    gas_exposure_environment  = get('gas_exposure_environment')
    duration_value            = get('duration_value')
    duration_unit             = get('duration_unit')
    long_term_exposure_type   = get('long_term_exposure_type')
    criterion_value           = get('criterion_value')
    mass_control_type         = get('mass_control_type')
    periodicity_text          = get('periodicity_text')
    periodicity_unit          = get('periodicity_unit')
    method_text               = get('method_text')

    if _has_value(temperature_c):
        parts.append(f"Температура: {_fmt_num(temperature_c)} °C")

    if _has_value(relative_humidity_percent):
        parts.append(f"Относительная влажность: {_fmt_num(relative_humidity_percent)} %")

    if water_exposure:
        parts.append("Выдержка в воде")

    if boiling_water_exposure:
        parts.append("Выдержка в кипящей воде")

    if _has_text(other_fluid_medium):
        parts.append(f"Другая текучая среда: {_clean(other_fluid_medium)}")

    if _has_text(gas_exposure_environment):
        parts.append(
            f"Выдержка в атмосфере газов, отличной от окружающей среды: "
            f"{_clean(gas_exposure_environment)}"
        )

    duration_str = _join_value_unit(duration_value, duration_unit)
    if duration_str:
        parts.append(f"Длительность: {duration_str}")

    if _has_text(long_term_exposure_type):
        parts.append(f"Тип длительной выдержки: {_clean(long_term_exposure_type)}")

    if _has_value(criterion_value):
        parts.append(f"Критерий: {_fmt_num(criterion_value)}")

    if _has_text(mass_control_type):
        parts.append(f"Тип контроля массы: {_clean(mass_control_type)}")

    periodicity_str = _join_text_unit(periodicity_text, periodicity_unit)
    if periodicity_str:
        parts.append(f"Периодичность: {periodicity_str}")

    if _has_text(method_text):
        parts.append(f"Метод: {_clean(method_text)}")

    result = '; '.join(parts)

    if max_length and len(result) > max_length:
        raise ValidationError(
            f'Сформированное поле "Условия испытания" слишком длинное: '
            f'{len(result)} символов при максимуме {max_length}.'
        )

    return result


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (ПРИВАТНЫЕ)
# =============================================================================

def _has_value(value) -> bool:
    return value is not None and value != ''


def _has_text(value) -> bool:
    return bool(str(value or '').strip())


def _clean(value) -> str:
    return ' '.join(str(value).strip().split())


def _fmt_num(value) -> str:
    """
    Красиво форматирует число:
    23.00 → '23'
    23.50 → '23,5'
    """
    if value is None or value == '':
        return ''

    if isinstance(value, Decimal):
        text = format(value, 'f')
    else:
        text = str(value).strip().replace(',', '.')

    if '.' in text:
        text = text.rstrip('0').rstrip('.')

    return text.replace('.', ',')


def _join_value_unit(value, unit) -> str:
    value_part = _fmt_num(value) if _has_value(value) else ''
    unit_part  = _clean(unit)   if _has_text(unit)  else ''

    if value_part and unit_part:
        return f"{value_part} {unit_part}"
    return value_part or unit_part


def _join_text_unit(text, unit) -> str:
    text_part = _clean(text) if _has_text(text) else ''
    unit_part = _clean(unit) if _has_text(unit) else ''

    if text_part and unit_part:
        return f"{text_part} {unit_part}"
    return text_part or unit_part


# =============================================================================
# ФОРМА ДЛЯ МОДАЛКИ
# =============================================================================

class GostR56762ParamsForm(forms.ModelForm):
    """
    Форма для модалки с параметрами испытания по ГОСТ Р 56762.
    Используется при создании и редактировании образца.

    Использование в view:
        gost_form = GostR56762ParamsForm(request.POST, prefix='gost56762')
        if gost_form.is_valid():
            params = gost_form.save(sample=sample)
            sample.test_conditions = gost_form.build_test_conditions()
            sample.save(update_fields=['test_conditions'])
    """

    class Meta:
        model  = SampleGostR56762Params
        fields = [
            'temperature_c',
            'relative_humidity_percent',
            'water_exposure',
            'boiling_water_exposure',
            'other_fluid_medium',
            'gas_exposure_environment',
            'duration_value',
            'duration_unit',
            'long_term_exposure_type',
            'criterion_value',
            'mass_control_type',
            'periodicity_text',
            'periodicity_unit',
            'method_text',
        ]
        widgets = {
            'temperature_c': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Например: 23',
            }),
            'relative_humidity_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': 'Например: 50',
            }),
            'water_exposure': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'boiling_water_exposure': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'other_fluid_medium': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Например: дистиллированная вода',
            }),
            'gas_exposure_environment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Укажите состав среды / газа',
            }),
            'duration_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Например: 24',
            }),
            'duration_unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: ч, сут, мин',
            }),
            'long_term_exposure_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: непрерывная',
            }),
            'criterion_value': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Например: 5',
            }),
            'mass_control_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: периодический',
            }),
            'periodicity_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: 1 3 6 7 или 1, 4, 5',
            }),
            'periodicity_unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Например: сут',
            }),
            'method_text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Укажите метод',
            }),
        }

    # Текстовые поля, которые нужно нормализовать
    _TEXT_FIELDS = (
        'other_fluid_medium',
        'gas_exposure_environment',
        'duration_unit',
        'long_term_exposure_type',
        'mass_control_type',
        'periodicity_text',
        'periodicity_unit',
        'method_text',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Все поля необязательны — бизнес-логика в clean()
        for field in self.fields.values():
            field.required = False

    # ------------------------------------------------------------------
    # Валидация отдельных полей
    # ------------------------------------------------------------------

    def clean_temperature_c(self):
        value = self.cleaned_data.get('temperature_c')
        if value is not None and value < -273.15:
            raise ValidationError('Температура не может быть ниже абсолютного нуля.')
        return value

    def clean_relative_humidity_percent(self):
        value = self.cleaned_data.get('relative_humidity_percent')
        if value is not None and not (0 <= value <= 100):
            raise ValidationError('Относительная влажность должна быть от 0 до 100%.')
        return value

    def clean_duration_value(self):
        value = self.cleaned_data.get('duration_value')
        if value is not None and value < 0:
            raise ValidationError('Длительность не может быть отрицательной.')
        return value

    # ------------------------------------------------------------------
    # Общая валидация
    # ------------------------------------------------------------------

    def clean(self):
        cleaned_data = super().clean()

        # Нормализуем все текстовые поля
        for field_name in self._TEXT_FIELDS:
            value = cleaned_data.get(field_name)
            if isinstance(value, str):
                cleaned_data[field_name] = _clean(value)

        duration_value   = cleaned_data.get('duration_value')
        duration_unit    = cleaned_data.get('duration_unit')
        periodicity_text = cleaned_data.get('periodicity_text')
        periodicity_unit = cleaned_data.get('periodicity_unit')

        # Длительность: значение и единицы должны быть вместе
        if duration_value is not None and not duration_unit:
            self.add_error('duration_unit', 'Укажите единицы измерения длительности.')
        if duration_unit and duration_value is None:
            self.add_error('duration_value', 'Укажите значение длительности.')

        # Периодичность: текст и единицы должны быть вместе
        if periodicity_text and not periodicity_unit:
            self.add_error('periodicity_unit', 'Укажите единицы измерения периодичности.')
        if periodicity_unit and not periodicity_text:
            self.add_error('periodicity_text', 'Укажите периодичность.')

        return cleaned_data

    # ------------------------------------------------------------------
    # Удобные методы
    # ------------------------------------------------------------------

    def build_test_conditions(self) -> str:
        """
        Собирает строку для Sample.test_conditions из cleaned_data.
        Вызывать только после успешного is_valid().
        """
        if not hasattr(self, 'cleaned_data'):
            raise ValueError('Сначала вызовите form.is_valid().')
        if self.errors:
            raise ValueError('Нельзя строить условия для невалидной формы.')

        return build_test_conditions_gost_r_56762(self.cleaned_data)

    def save(self, *, sample=None, commit=True):
        """
        Сохраняет запись в sample_gost_r_56762_params.

        Пример:
            params = gost_form.save(sample=sample)
        """
        instance = super().save(commit=False)

        if sample is not None:
            instance.sample = sample

        if not getattr(instance, 'sample_id', None):
            raise ValueError(
                'Для сохранения GostR56762ParamsForm нужно передать sample=...'
            )

        if commit:
            instance.save()

        return instance