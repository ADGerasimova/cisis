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
# CHOICES ДЛЯ ГОСТ Р 56762
# =============================================================================

EMPTY_CHOICE = [('', '—')]

DURATION_UNIT_CHOICES = EMPTY_CHOICE + [
    ('HOUR', 'час'),
    ('DAY', 'день/сутки'),
    ('MONTH', 'месяц'),
]

LONG_TERM_EXPOSURE_TYPE_CHOICES = EMPTY_CHOICE + [
    ('MAX_TIME', 'Выдержка не более определённого времени'),
    ('FIXED_DURATION', 'Выдержка фиксированной продолжительности'),
]

MASS_CONTROL_TYPE_CHOICES = EMPTY_CHOICE + [
    ('BEFORE_AFTER', 'До и после испытания'),
    ('STANDARD_WEEKLY', 'Стандартное измерение (раз в неделю)'),
    ('STANDARD_WEEKLY_PLUS_CUSTOM', 'Стандартное измерение + указанная периодичность'),
    ('CUSTOM', 'Указанная периодичность'),
    ('WITHOUT_CONTROL', 'Без контроля'),
]

PERIODICITY_UNIT_CHOICES = EMPTY_CHOICE + [
    ('HOUR', 'час'),
    ('DAY', 'день/сутки'),
]

DURATION_UNIT_LABELS = dict(DURATION_UNIT_CHOICES)
LONG_TERM_EXPOSURE_TYPE_LABELS = dict(LONG_TERM_EXPOSURE_TYPE_CHOICES)
MASS_CONTROL_TYPE_LABELS = dict(MASS_CONTROL_TYPE_CHOICES)
PERIODICITY_UNIT_LABELS = dict(PERIODICITY_UNIT_CHOICES)

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


def _choice_label(value, labels_map) -> str:
    if not _has_text(value):
        return ''
    return labels_map.get(str(value).strip(), str(value).strip())

# =============================================================================
# СКЛОНЕНИЯ ЕДИНИЦ ДЛЯ ФРАЗ ВИДА "24 часа", "90 суток", "1 месяц"
# =============================================================================

# Формы (1 / 2-4 / 5+) для единиц длительности.
# Используются после числа в "в течение N ..." и "Выдержка не более N ...".
_DURATION_UNIT_FORMS = {
    'HOUR':  ('час',   'часа',   'часов'),
    'DAY':   ('сутки', 'суток',  'суток'),
    'MONTH': ('месяц', 'месяца', 'месяцев'),
}

# Единицы периодичности в контроле массы — не склоняются,
# т.к. по смыслу идёт перечисление ("1, 3, 10 дней испытания").
_PERIODICITY_UNIT_WORDS = {
    'HOUR': 'часа',
    'DAY':  'дней',
}


# =============================================================================
# ГЕНЕРАЦИЯ СТРОКИ test_conditions
# =============================================================================

def build_test_conditions_gost_r_56762(
    data,
    *,
    max_length=SAMPLE_TEST_CONDITIONS_MAX_LENGTH,
) -> str:
    """
    Собирает строку для Sample.test_conditions из параметров ГОСТ Р 56762.

    Структура:
        1. Среда выдержки + " по методу X" + " при температуре: NC и
           относительной влажности: M%"
        2. Длительность:
           - FIXED_DURATION:  продолжает фразу -> "... в течение N часов"
           - MAX_TIME:        новое предложение -> "Выдержка не более N часов"
        3. Контроль массы — отдельное предложение.
        4. Критерий равновесного влагонасыщения — отдельное предложение.

    data может быть dict (form.cleaned_data) или объект SampleGostR56762Params.
    """

    def get(field_name):
        if isinstance(data, dict):
            return data.get(field_name)
        return getattr(data, field_name, None)

    # ------------------------------------------------------------------
    # Извлечение полей
    # ------------------------------------------------------------------
    water_exposure            = bool(get('water_exposure'))
    boiling_water_exposure    = bool(get('boiling_water_exposure'))
    other_fluid_medium        = get('other_fluid_medium')
    gas_exposure_environment  = get('gas_exposure_environment')
    method_text               = get('method_text')
    temperature_c             = get('temperature_c')
    relative_humidity_percent = get('relative_humidity_percent')
    long_term_exposure_type   = (get('long_term_exposure_type') or '').strip()
    duration_value            = get('duration_value')
    duration_unit_code        = (get('duration_unit') or '').strip()
    mass_control_type         = (get('mass_control_type') or '').strip()
    periodicity_text          = get('periodicity_text')
    periodicity_unit_code     = (get('periodicity_unit') or '').strip()
    criterion_value           = get('criterion_value')

    # ------------------------------------------------------------------
    # Основное предложение: среда + метод + температура/влажность
    # ------------------------------------------------------------------

    # Пункт 1 — среда выдержки
    medium_parts = []
    if water_exposure:
        medium_parts.append('Выдержка в воде')
    if boiling_water_exposure:
        medium_parts.append('Выдержка в кипящей воде')
    if _has_text(other_fluid_medium):
        medium_parts.append(_clean(other_fluid_medium))
    if _has_text(gas_exposure_environment):
        medium_parts.append(_clean(gas_exposure_environment))

    main_sentence = ', '.join(medium_parts)

    # Пункт 2.1 — метод ("по методу X")
    if _has_text(method_text):
        method_str = f'по методу {_clean(method_text)}'
        if main_sentence:
            main_sentence = f'{main_sentence} {method_str}'
        else:
            # Если среды не задано — начинаем с дефолтного "Выдержка по методу"
            main_sentence = f'Выдержка {method_str}'

    # Пункт 2.2 — температура и относительная влажность
    temp_str = f'{_fmt_num(temperature_c)}C'             if _has_value(temperature_c) else ''
    hum_str  = f'{_fmt_num(relative_humidity_percent)}%' if _has_value(relative_humidity_percent) else ''

    conditions_str = ''
    if temp_str and hum_str:
        conditions_str = (
            f'при температуре: {temp_str} и '
            f'относительной влажности: {hum_str}'
        )
    elif temp_str:
        conditions_str = f'при температуре: {temp_str}'
    elif hum_str:
        conditions_str = f'при относительной влажности: {hum_str}'

    if conditions_str:
        if main_sentence:
            main_sentence = f'{main_sentence} {conditions_str}'
        else:
            main_sentence = conditions_str  # начнётся с "при ..." — capitalize ниже

    # Первая буква основного предложения — заглавная
    if main_sentence:
        main_sentence = _capitalize_first(main_sentence)

    # ------------------------------------------------------------------
    # Пункт 3 — тип длительной выдержки
    # ------------------------------------------------------------------
    duration_str = _format_duration(duration_value, duration_unit_code)

    sentences = []  # законченные предложения без финальной точки

    if long_term_exposure_type == 'FIXED_DURATION' and duration_str:
        # "... в течение X часов" — продолжение основного предложения
        if main_sentence:
            sentences.append(f'{main_sentence} в течение {duration_str}')
        else:
            sentences.append(f'В течение {duration_str}')
    elif long_term_exposure_type == 'MAX_TIME' and duration_str:
        # Основное — отдельно, затем "Выдержка не более X часов" новым предложением
        if main_sentence:
            sentences.append(main_sentence)
        sentences.append(f'Выдержка не более {duration_str}')
    else:
        # Тип выдержки не задан или нет длительности — только основное
        if main_sentence:
            sentences.append(main_sentence)

    # ------------------------------------------------------------------
    # Пункт 4 — контроль массы
    # ------------------------------------------------------------------
    mass_sentence = _build_mass_sentence(
        mass_control_type, periodicity_text, periodicity_unit_code,
    )
    if mass_sentence:
        sentences.append(mass_sentence)

    # ------------------------------------------------------------------
    # Пункт 5 — критерий равновесного влагонасыщения
    # ------------------------------------------------------------------
    if _has_value(criterion_value):
        sentences.append(
            f'Критерий равновесного влагонасыщения {_fmt_num(criterion_value)}%'
        )

    # ------------------------------------------------------------------
    # Склейка: предложения через ". ", в конце — точка
    # ------------------------------------------------------------------
    result = '. '.join(sentences)
    if result and not result.endswith('.'):
        result += '.'

    if max_length and len(result) > max_length:
        raise ValidationError(
            f'Сформированное поле "Условия испытания" слишком длинное: '
            f'{len(result)} символов при максимуме {max_length}.'
        )

    return result


def _format_duration(value, unit_code: str) -> str:
    """
    Форматирует длительность со склонением по числу: "24 часа", "90 суток".
    Возвращает пустую строку, если значение или единица не заданы.
    """
    if not _has_value(value):
        return ''
    forms = _DURATION_UNIT_FORMS.get(unit_code)
    if not forms:
        return ''
    return f'{_fmt_num(value)} {_plural_ru(value, forms)}'


def _build_mass_sentence(
    mass_control_type: str,
    periodicity_text,
    periodicity_unit_code: str,
) -> str:
    """
    Собирает предложение про контроль массы (без финальной точки).
    Для CUSTOM / STANDARD_WEEKLY_PLUS_CUSTOM без заполненной периодичности —
    аккуратно деградирует.
    """
    if not mass_control_type:
        return ''

    periodicity_word = _PERIODICITY_UNIT_WORDS.get(periodicity_unit_code, '')
    has_periodicity  = _has_text(periodicity_text) and bool(periodicity_word)

    if mass_control_type == 'WITHOUT_CONTROL':
        return 'Измерения массы не требуются'

    if mass_control_type == 'BEFORE_AFTER':
        return 'Измерения массы до и после испытания'

    if mass_control_type == 'STANDARD_WEEKLY':
        return 'Измерять массу каждые 7 дней'

    if mass_control_type == 'CUSTOM':
        if has_periodicity:
            return (
                f'Измерять массу по прошествии '
                f'{_clean(periodicity_text)} {periodicity_word} испытания'
            )
        return ''  # периодичность обязательна для этого типа

    if mass_control_type == 'STANDARD_WEEKLY_PLUS_CUSTOM':
        if has_periodicity:
            return (
                f'Измерять массу каждые 7 дней и дополнительно по прошествии '
                f'{_clean(periodicity_text)} {periodicity_word} испытания'
            )
        return 'Измерять массу каждые 7 дней'

    return ''


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


def _plural_ru(value, forms) -> str:
    """
    Выбирает форму существительного по числу.

    forms = (one, few, many), например:
        ('час',   'часа',   'часов')
        ('сутки', 'суток',  'суток')
        ('месяц', 'месяца', 'месяцев')

    Правила:
    - Дробное число → форма "few" (как в "1,5 часа", "0,5 месяца").
    - Целое, оканчивается на 1 (кроме 11): "one".
    - Целое, оканчивается на 2–4 (кроме 12–14): "few".
    - Остальное: "many".
    """
    try:
        num = float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return forms[2]

    # Дробное число — всегда форма родительного ед.ч. ("2,5 часа")
    if num != int(num):
        return forms[1]

    n = abs(int(num))
    last_two = n % 100
    if 11 <= last_two <= 14:
        return forms[2]

    last = n % 10
    if last == 1:
        return forms[0]
    if 2 <= last <= 4:
        return forms[1]
    return forms[2]


def _capitalize_first(s: str) -> str:
    """Делает заглавной первую букву, остальную часть строки не трогает."""
    if not s:
        return s
    return s[0].upper() + s[1:]


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

    duration_unit = forms.ChoiceField(
        required=False,
        choices=DURATION_UNIT_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
        })
    )

    long_term_exposure_type = forms.ChoiceField(
        required=False,
        choices=LONG_TERM_EXPOSURE_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
        })
    )

    mass_control_type = forms.ChoiceField(
        required=False,
        choices=MASS_CONTROL_TYPE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
        })
    )

    periodicity_unit = forms.ChoiceField(
        required=False,
        choices=PERIODICITY_UNIT_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control',
        })
    )

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
        long_term_exposure_type = cleaned_data.get('long_term_exposure_type')
        mass_control_type = cleaned_data.get('mass_control_type')

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

        # Тип длительной выдержки требует длительность + единицы
        if long_term_exposure_type:
            if duration_value is None:
                self.add_error(
                    'duration_value',
                    'Для выбранного типа длительной выдержки укажите длительность.',
                )
            if not duration_unit:
                self.add_error(
                    'duration_unit',
                    'Для выбранного типа длительной выдержки укажите единицы измерения.',
                )

        # CUSTOM / STANDARD_WEEKLY_PLUS_CUSTOM требуют заполненную периодичность
        if mass_control_type in ('CUSTOM', 'STANDARD_WEEKLY_PLUS_CUSTOM'):
            if not periodicity_text:
                self.add_error(
                    'periodicity_text',
                    'Для выбранного типа контроля массы укажите периодичность.',
                )
            if not periodicity_unit:
                self.add_error(
                    'periodicity_unit',
                    'Для выбранного типа контроля массы укажите единицы измерения периодичности.',
                )

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