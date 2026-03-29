"""
s3_utils.py — Утилиты для работы с S3 Object Storage (REG.Cloud)
v3.44.0

Единый интерфейс для загрузки, скачивания и удаления файлов в S3.
Используется во всех view, которые работают с файлами.

Файловая структура в бакете:
    chat/YYYY-MM/<uuid>.<ext>
    avatars/<user_id>_<hash>.<ext>
    feedback/YYYY-MM/screenshot_<user_id>_<ts>.<ext>
    files/<category>/<entity>/...            (основная файловая система)
"""

import os
import uuid
import logging
from io import BytesIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_client():
    """Возвращает настроенный boto3 S3 клиент (singleton-подобный)."""
    if not hasattr(_get_client, '_client'):
        _get_client._client = boto3.client(
            's3',
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            verify=getattr(settings, 'AWS_S3_VERIFY', True),
            config=Config(
                signature_version='s3v4',
                s3={'addressing_style': 'path'},
            ),
        )
    return _get_client._client


def get_bucket():
    """Возвращает имя бакета из настроек."""
    return settings.AWS_STORAGE_BUCKET_NAME


# ═══════════════════════════════════════════════
# ЗАГРУЗКА
# ═══════════════════════════════════════════════

def upload_file(file_obj, s3_key, content_type=None):
    """
    Загружает файл (UploadedFile или file-like объект) в S3.

    Args:
        file_obj: Django UploadedFile или любой file-like объект с read()
        s3_key: путь в бакете, например 'chat/2026-03/abc123.jpg'
        content_type: MIME-тип (опционально)

    Returns:
        s3_key при успехе, None при ошибке
    """
    s3 = _get_client()
    extra_args = {}
    if content_type:
        extra_args['ContentType'] = content_type

    try:
        # Django UploadedFile → читаем в память
        if hasattr(file_obj, 'chunks'):
            body = b''.join(file_obj.chunks())
        elif hasattr(file_obj, 'read'):
            body = file_obj.read()
        else:
            body = file_obj  # bytes

        s3.put_object(
            Bucket=get_bucket(),
            Key=s3_key,
            Body=body,
            **extra_args,
        )
        logger.info(f'S3 upload OK: {s3_key} ({len(body)} bytes)')
        return s3_key
    except ClientError as e:
        logger.error(f'S3 upload FAILED: {s3_key} — {e}')
        return None


def upload_bytes(data: bytes, s3_key: str, content_type=None):
    """
    Загружает байты напрямую в S3.

    Args:
        data: байты для загрузки
        s3_key: путь в бакете
        content_type: MIME-тип (опционально)

    Returns:
        s3_key при успехе, None при ошибке
    """
    return upload_file(data, s3_key, content_type)


# ═══════════════════════════════════════════════
# СКАЧИВАНИЕ
# ═══════════════════════════════════════════════

def download_file(s3_key):
    """
    Скачивает файл из S3 и возвращает байты.

    Returns:
        bytes при успехе, None при ошибке
    """
    s3 = _get_client()
    try:
        response = s3.get_object(Bucket=get_bucket(), Key=s3_key)
        return response['Body'].read()
    except ClientError as e:
        logger.error(f'S3 download FAILED: {s3_key} — {e}')
        return None


def get_presigned_url(s3_key, expires_in=3600, content_type=None):
    """
    Генерирует подписанный URL для скачивания файла.

    Args:
        s3_key: путь в бакете
        expires_in: время жизни URL в секундах (по умолчанию 1 час)
        content_type: Content-Type для ответа

    Returns:
        URL строка или None при ошибке
    """
    s3 = _get_client()
    params = {
        'Bucket': get_bucket(),
        'Key': s3_key,
    }
    if content_type:
        params['ResponseContentType'] = content_type

    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params=params,
            ExpiresIn=expires_in,
        )
        return url
    except ClientError as e:
        logger.error(f'S3 presigned URL FAILED: {s3_key} — {e}')
        return None


# ═══════════════════════════════════════════════
# УДАЛЕНИЕ
# ═══════════════════════════════════════════════

def delete_file(s3_key):
    """
    Удаляет файл из S3.

    Returns:
        True при успехе, False при ошибке
    """
    s3 = _get_client()
    try:
        s3.delete_object(Bucket=get_bucket(), Key=s3_key)
        logger.info(f'S3 delete OK: {s3_key}')
        return True
    except ClientError as e:
        logger.error(f'S3 delete FAILED: {s3_key} — {e}')
        return False


# ═══════════════════════════════════════════════
# ПРОВЕРКА
# ═══════════════════════════════════════════════

def file_exists(s3_key):
    """
    Проверяет, существует ли файл в S3.

    Returns:
        True если файл существует, False если нет
    """
    s3 = _get_client()
    try:
        s3.head_object(Bucket=get_bucket(), Key=s3_key)
        return True
    except ClientError:
        return False


# ═══════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ
# ═══════════════════════════════════════════════

def generate_s3_key(prefix, filename):
    """
    Генерирует уникальный S3-ключ с сохранением расширения.

    Args:
        prefix: папка в бакете, например 'chat/2026-03'
        filename: оригинальное имя файла

    Returns:
        Строка вида 'chat/2026-03/a1b2c3d4e5f6.jpg'
    """
    ext = os.path.splitext(filename)[1].lower()
    unique_name = f'{uuid.uuid4().hex}{ext}'
    return f'{prefix}/{unique_name}'


def is_s3_enabled():
    """Проверяет, настроено ли S3 хранилище."""
    return bool(
        getattr(settings, 'AWS_ACCESS_KEY_ID', None) and
        getattr(settings, 'AWS_SECRET_ACCESS_KEY', None) and
        getattr(settings, 'AWS_STORAGE_BUCKET_NAME', None)
    )
