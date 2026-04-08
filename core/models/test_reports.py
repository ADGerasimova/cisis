"""
core/models/test_reports.py

Модели для отчётов об испытаниях:
- ReportTemplateSource — xlsx-файлы с шаблонами
- ReportTemplateIndex  — маппинг стандарт → блок в xlsx
- TestReport           — конкретный отчёт (JSONB + ключевые показатели)
"""

from django.db import models


class ReportTemplateSource(models.Model):
    """Xlsx-файл с шаблонами таблиц (один файл = много стандартов)."""

    laboratory = models.ForeignKey(
        'Laboratory', on_delete=models.SET_NULL, null=True, blank=True,
        db_column='laboratory_id', related_name='report_template_sources',
    )
    file_name = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    description = models.TextField(default='', blank=True)
    uploaded_by = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True,
        db_column='uploaded_by_id', related_name='uploaded_template_sources',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'report_template_sources'

    def __str__(self):
        return f'{self.file_name} ({self.laboratory})'


class ReportTemplateIndex(models.Model):
    """Маппинг: стандарт → блок в xlsx-файле + конфигурация столбцов. Версионируется."""

    LAYOUT_CHOICES = [
        ('A', 'Тип A — стандартный'),
        ('B', 'Тип B — с боковой таблицей замеров'),
        ('C', 'Тип C — расширенный'),
    ]

    standard = models.ForeignKey(
        'Standard', on_delete=models.CASCADE,
        db_column='standard_id', related_name='report_templates',
    )
    source = models.ForeignKey(
        'ReportTemplateSource', on_delete=models.CASCADE,
        db_column='source_id', related_name='templates',
        null=True, blank=True,  # ← Добавь null=True если source может быть пустым
    )
    sheet_name = models.CharField(max_length=255)
    start_row = models.IntegerField()
    end_row = models.IntegerField()
    header_row = models.IntegerField()
    data_start_row = models.IntegerField()
    stats_start_row = models.IntegerField(null=True, blank=True)

    # Конфигурация (JSONB, заполняется парсером)
    column_config = models.JSONField(default=list)
    header_config = models.JSONField(default=dict)
    statistics_config = models.JSONField(default=list)
    sub_measurements_config = models.JSONField(null=True, blank=True)
    
    # ═══ ДОБАВЬ ЭТО ПОЛЕ ═══
    additional_tables = models.JSONField(null=True, blank=True)
    # ════════════════════════

    layout_type = models.CharField(max_length=10, choices=LAYOUT_CHOICES, default='A')

    # Версионирование
    version = models.IntegerField(default=1)
    is_current = models.BooleanField(default=True)
    changes_description = models.TextField(default='', blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        db_table = 'report_template_index'
        unique_together = [('standard', 'version')]

    def __str__(self):
        return f'Template: {self.standard} v{self.version} ({"текущий" if self.is_current else "архив"})'

    @property
    def input_columns(self):
        """Столбцы, которые оператор вводит вручную."""
        return [c for c in self.column_config if c.get('type') == 'INPUT']

    @property
    def calculated_columns(self):
        """Вычисляемые столбцы."""
        return [c for c in self.column_config if c.get('type') in ('CALCULATED', 'SUB_AVG')]

    @property
    def has_sub_measurements(self):
        """Есть ли боковая таблица промежуточных замеров."""
        # Проверяем оба варианта
        if self.sub_measurements_config:
            return True
        if self.additional_tables:
            for at in self.additional_tables:
                if at.get('table_type') == 'SUB_MEASUREMENTS':
                    return True
        return False

class TestReport(models.Model):
    """
    Отчёт об испытании.
    Одна строка = одно полное испытание со всеми образцами.
    """

    STATUS_CHOICES = [
        ('DRAFT', 'Черновик'),
        ('COMPLETED', 'Завершён'),
        ('APPROVED', 'Утверждён'),
    ]

    sample = models.ForeignKey(
        'Sample', on_delete=models.CASCADE,
        db_column='sample_id', related_name='test_reports',
    )
    standard = models.ForeignKey(
        'Standard', on_delete=models.RESTRICT,
        db_column='standard_id', related_name='test_reports',
    )
    template = models.ForeignKey(
        'ReportTemplateIndex', on_delete=models.SET_NULL,
        null=True, blank=True,
        db_column='template_id', related_name='reports',
    )
    created_by = models.ForeignKey(
        'User', on_delete=models.SET_NULL, null=True, blank=True,
        db_column='created_by_id', related_name='created_test_reports',
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')

    # Данные (JSONB)
    header_data = models.JSONField(default=dict)
    table_data = models.JSONField(default=dict)
    statistics_data = models.JSONField(default=dict)

    # ═══ ДОБАВЬ ЭТИ ДВА ПОЛЯ ═══
    export_settings = models.JSONField(null=True, blank=True)
    additional_tables_data = models.JSONField(null=True, blank=True)
    # ═════════════════════════════

    # Ключевые показатели для аналитики
    specimen_count = models.IntegerField(null=True, blank=True)
    mean_strength = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    mean_modulus = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    mean_elongation = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    cv_strength = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False          # ← Таблица уже существует в БД
        db_table = 'test_reports'
        ordering = ['-created_at']

    def __str__(self):
        return f'Report #{self.id}: {self.sample} / {self.standard}'

    @property
    def specimens(self):
        return self.table_data.get('specimens', [])

    @property
    def specimen_numbers(self):
        return [s.get('number') for s in self.specimens]

    def get_column_values(self, column_code):
        values = []
        for specimen in self.specimens:
            v = specimen.get('values', {}).get(column_code)
            if v is not None:
                values.append(v)
        return values

    def get_statistic(self, column_code, stat_type='mean'):
        col_stats = self.statistics_data.get(column_code, {})
        return col_stats.get(stat_type)

    def extract_key_metrics(self):
        self.specimen_count = len(self.specimens)

        strength_codes = ['sigma', 'sigma_v', 'Ftu', 'sigma_pm', 'fp', 'F_mpa']
        for code in strength_codes:
            stats = self.statistics_data.get(code, {})
            if stats.get('mean') is not None:
                self.mean_strength = stats['mean']
                self.cv_strength = stats.get('cv')
                break

        for code in ['E', 'Ep', 'E_gpa']:
            stats = self.statistics_data.get(code, {})
            if stats.get('mean') is not None:
                self.mean_modulus = stats['mean']
                break

        for code in ['delta', 'epsilon', 'epsilon_r', 'elongation']:
            stats = self.statistics_data.get(code, {})
            if stats.get('mean') is not None:
                self.mean_elongation = stats['mean']
                break