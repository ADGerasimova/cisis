"""
Модель для работы с файлами образцов
"""

from django.db import models


# =============================================================================
# ФАЙЛЫ ОБРАЗЦОВ
# =============================================================================

class SampleFile(models.Model):
    """
    Файлы, привязанные к образцам (протоколы, фотографии, отчёты и т.д.)

    Физическое хранение:
    D:/CISIS_Files/Выходные данные лабораторий/{laboratory.code}/{YYYY}/{sequence_number}/

    Например:
    D:/CISIS_Files/Выходные данные лабораторий/MI/2026/001/protocol_001.pdf
    """

    sample = models.ForeignKey(
        'Sample',
        on_delete=models.CASCADE,
        related_name='files',
        verbose_name='Образец'
    )

    file = models.FileField(
        upload_to='',  # Путь генерируется динамически в save()
        verbose_name='Файл',
        max_length=500
    )

    original_filename = models.CharField(
        max_length=255,
        verbose_name='Исходное имя файла'
    )

    file_size = models.BigIntegerField(
        verbose_name='Размер файла (байты)'
    )

    uploaded_by = models.ForeignKey(
        'User',
        on_delete=models.RESTRICT,
        related_name='uploaded_files',
        db_column='uploaded_by_id',
        verbose_name='Загрузил'
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата загрузки'
    )

    description = models.CharField(
        max_length=500,
        default='',
        blank=True,
        verbose_name='Описание'
    )

    class Meta:
        db_table = 'sample_files'
        managed = True  # Django будет создавать эту таблицу через миграцию
        ordering = ['-uploaded_at']
        verbose_name = 'Файл образца'
        verbose_name_plural = 'Файлы образцов'

    def __str__(self):
        return f'{self.original_filename} ({self.sample})'

    # ═══════════════════════════════════════════════════════════════
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ═══════════════════════════════════════════════════════════════

    def get_file_extension(self):
        """Возвращает расширение файла"""
        import os
        return os.path.splitext(self.original_filename)[1].lower()

    def is_image(self):
        """Проверяет, является ли файл изображением"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        return self.get_file_extension() in image_extensions

    def is_pdf(self):
        """Проверяет, является ли файл PDF"""
        return self.get_file_extension() == '.pdf'

    def get_size_display(self):
        """Возвращает размер файла в читаемом формате"""
        size = self.file_size
        for unit in ['Б', 'КБ', 'МБ', 'ГБ']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} ТБ"
