"""
Views для файловой системы CISIS v3.44.0

Загрузка, скачивание, удаление, замена (версионность).
Проверка доступа через PermissionChecker + file_visibility_rules.

v3.44.0: Все файлы хранятся в S3 Object Storage (REG.Cloud).
"""

import os
import re
import mimetypes
from io import BytesIO

from django.conf import settings
from django.http import (
    JsonResponse, HttpResponse, FileResponse, Http404
)
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from urllib.parse import quote

from core.models import File, FileTypeDefault, FileVisibilityRule, PersonalFolderAccess
from core.models.files import FileCategory, FileType, FileVisibility
from core.permissions import PermissionChecker
from core.views.audit import log_action


# =============================================================================
# КОНСТАНТЫ
# =============================================================================

MAX_FILE_SIZE = int(getattr(settings, 'FILE_MAX_SIZE_MB', 50)) * 1024 * 1024

ALLOWED_EXTENSIONS = set(
    getattr(settings, 'FILE_ALLOWED_EXTENSIONS',
            'pdf,jpg,jpeg,png,gif,webp,xlsx,xls,docx,doc,csv,txt,zip,rar').split(',')
)

THUMBNAIL_SIZE = (200, 200)


# =============================================================================
# ПРОВЕРКА ДОСТУПА
# =============================================================================

def _get_files_column(category):
    """Возвращает имя столбца в журнале FILES для данной категории"""
    mapping = {
        FileCategory.SAMPLE: 'samples_files',
        FileCategory.CLIENT: 'clients_files',
        FileCategory.EQUIPMENT: 'equipment_files',
        FileCategory.STANDARD: 'standards_files',
        FileCategory.QMS: 'qms_files',
        FileCategory.PERSONAL: 'personal_files',
        FileCategory.INBOX: 'inbox_files',
    }
    return mapping.get(category, 'samples_files')


def _can_view_file(user, file_obj):
    """
    Проверяет, может ли пользователь видеть файл.
    Три уровня: категория → сущность → тип файла.
    """
    # 1. Доступ к категории
    column = _get_files_column(file_obj.category)
    if not PermissionChecker.can_view(user, 'FILES', column):
        return False

    # 2. Доступ к сущности
    if file_obj.sample_id:
        if not PermissionChecker.has_journal_access(user, 'SAMPLES'):
            return False
    if file_obj.acceptance_act_id or file_obj.contract_id:
        if not PermissionChecker.can_view(user, 'CLIENTS', 'access'):
            return False

    # 3. Личные папки
    if file_obj.category == FileCategory.PERSONAL:
        if file_obj.owner_id == user.id:
            return True
        return PersonalFolderAccess.objects.filter(
            owner_id=file_obj.owner_id,
            granted_to_id=user.id
        ).exists()

    # 4. Видимость типа файла
    if file_obj.visibility == FileVisibility.RESTRICTED:
        blocked = FileVisibilityRule.objects.filter(
            file_type=file_obj.file_type,
            category=file_obj.category,
            role=user.role
        ).exists()
        if blocked:
            return False

    # 5. Приватные файлы
    if file_obj.visibility == FileVisibility.PRIVATE:
        if file_obj.uploaded_by_id != user.id and file_obj.owner_id != user.id:
            return False

    return True


def _can_edit_file(user, file_obj):
    """Может ли пользователь редактировать/удалять файл"""
    column = _get_files_column(file_obj.category)
    if not PermissionChecker.can_edit(user, 'FILES', column):
        return False

    if file_obj.category == FileCategory.PERSONAL:
        if file_obj.owner_id == user.id:
            return True
        return PersonalFolderAccess.objects.filter(
            owner_id=file_obj.owner_id,
            granted_to_id=user.id,
            access_level='EDIT'
        ).exists()

    return True


def _can_upload_to_category(user, category):
    """Может ли пользователь загружать файлы в категорию"""
    column = _get_files_column(category)
    return PermissionChecker.can_edit(user, 'FILES', column)


# =============================================================================
# ПОЛУЧЕНИЕ ФАЙЛОВ ДЛЯ СУЩНОСТИ
# =============================================================================

def get_files_for_entity(user, entity_type, entity_id):
    """
    Возвращает файлы, привязанные к сущности, с учётом видимости.
    Используется в карточках образцов, актов и т.д.
    """
    filter_kwargs = {
        f'{entity_type}_id': entity_id,
        'is_deleted': False,
        'current_version': True,
    }
    files = File.objects.filter(**filter_kwargs).order_by('file_type', '-uploaded_at')

    visible_files = []
    hidden_types = set()

    for f in files:
        if _can_view_file(user, f):
            visible_files.append(f)
        else:
            hidden_types.add(f.file_type)

    grouped = {}
    for f in visible_files:
        if f.file_type not in grouped:
            grouped[f.file_type] = []
        grouped[f.file_type].append(f)

    return {
        'files': visible_files,
        'grouped': grouped,
        'hidden_types': hidden_types,
        'total_count': len(visible_files),
    }


# =============================================================================
# ЗАГРУЗКА ФАЙЛА
# =============================================================================

@login_required
@require_POST
def file_upload(request):
    """
    Загрузка файла в S3.

    POST параметры:
    - file: файл
    - category: категория (SAMPLE, CLIENT, ...)
    - file_type: тип файла (PHOTO, PROTOCOL, ...)
    - entity_type: тип сущности (sample, acceptance_act, contract, equipment, standard)
    - entity_id: ID сущности
    - description: описание (опционально)
    """
    user = request.user

    uploaded_file = request.FILES.get('file')
    category = request.POST.get('category', '')
    file_type = request.POST.get('file_type', '')
    entity_type = request.POST.get('entity_type', '')
    entity_id = request.POST.get('entity_id', '')
    description = request.POST.get('description', '')

    # Валидация
    if not uploaded_file:
        return JsonResponse({'error': 'Файл не выбран'}, status=400)

    if uploaded_file.size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE // (1024 * 1024)
        return JsonResponse({'error': f'Файл слишком большой (макс. {max_mb} МБ)'}, status=400)

    ext = os.path.splitext(uploaded_file.name)[1].lower().lstrip('.')
    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse({'error': f'Недопустимый формат файла (.{ext})'}, status=400)

    valid_categories = [c[0] for c in FileCategory.CHOICES]
    if category not in valid_categories:
        return JsonResponse({'error': 'Неверная категория'}, status=400)

    if not _can_upload_to_category(user, category):
        return JsonResponse({'error': 'Нет прав на загрузку в эту категорию'}, status=403)

    # Получаем сущность
    entity_obj = None
    if entity_type and entity_id:
        try:
            entity_id = int(entity_id)
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Неверный ID сущности'}, status=400)

        from core.models import Sample, AcceptanceAct, Contract, Equipment, Standard
        model_map = {
            'sample': (Sample, 'sample'),
            'acceptance_act': (AcceptanceAct, 'acceptance_act'),
            'contract': (Contract, 'contract'),
            'equipment': (Equipment, 'equipment'),
            'standard': (Standard, 'standard'),
        }
        if entity_type in model_map:
            model_class, field_name = model_map[entity_type]
            try:
                entity_obj = model_class.objects.get(id=entity_id)
            except model_class.DoesNotExist:
                return JsonResponse({'error': 'Сущность не найдена'}, status=404)

    # Генерация S3-ключа
    path_kwargs = {}
    if entity_obj:
        path_kwargs[entity_type] = entity_obj
    if category == FileCategory.PERSONAL:
        path_kwargs['user'] = user

    relative_dir = File.get_upload_path(category, file_type, **path_kwargs)
    safe_name = _safe_filename(uploaded_file.name)
    s3_key = f'{relative_dir}/{safe_name}'

    mime, _ = mimetypes.guess_type(uploaded_file.name)

    # ═══ S3 загрузка ═══
    from core.services.s3_utils import upload_file as s3_upload
    result = s3_upload(uploaded_file, s3_key, content_type=mime)
    if not result:
        return JsonResponse({'error': 'Ошибка загрузки файла'}, status=500)

    # Дефолтная видимость
    visibility = File.get_default_visibility(category, file_type)

    # Создаём запись в БД
    file_record = File(
        file_path=s3_key,
        original_name=uploaded_file.name,
        file_size=uploaded_file.size,
        mime_type=mime or '',
        category=category,
        file_type=file_type,
        visibility=visibility,
        description=description,
        uploaded_by=user,
    )

    # Привязка к сущности
    if entity_type == 'sample':
        file_record.sample = entity_obj
    elif entity_type == 'acceptance_act':
        file_record.acceptance_act = entity_obj
    elif entity_type == 'contract':
        file_record.contract = entity_obj
    elif entity_type == 'equipment':
        file_record.equipment = entity_obj
    elif entity_type == 'standard':
        file_record.standard = entity_obj

    # Личная папка
    if category == FileCategory.PERSONAL:
        file_record.owner = user
        # Привязка к подпапке (entity_id = ID личной папки)
        if entity_type == 'personal' and entity_id:
            from core.models.files import PersonalFolder
            try:
                pf = PersonalFolder.objects.get(id=int(entity_id), owner=user)
                file_record.personal_folder = pf
            except (ValueError, PersonalFolder.DoesNotExist):
                pass

    file_record.save()

    # Генерация миниатюры для изображений
    if file_record.is_image:
        _generate_thumbnail(file_record)

    # Аудит
    entity_audit_type = entity_type.upper() if entity_type else 'FILE'
    entity_audit_id = entity_id if entity_id else file_record.id
    log_action(
        request,
        entity_type=entity_audit_type,
        entity_id=entity_audit_id,
        action='FILE_UPLOAD',
        extra_data={'detail': f'Загружен файл: {uploaded_file.name} ({file_record.size_display}), тип: {file_type}'}
    )

    return JsonResponse({
        'success': True,
        'file_id': file_record.id,
        'file_name': file_record.original_name,
        'file_size': file_record.size_display,
        'file_type': file_record.file_type,
        'version': file_record.version,
    })


# =============================================================================
# СКАЧИВАНИЕ ФАЙЛА
# =============================================================================

@login_required
@require_GET
def file_download(request, file_id):
    """Скачивание файла с проверкой доступа (через S3 presigned URL)"""
    file_obj = get_object_or_404(File, id=file_id, is_deleted=False)

    if not _can_view_file(request.user, file_obj):
        return JsonResponse({'error': 'Нет доступа к файлу'}, status=403)

    # Аудит скачивания
    log_action(
        request,
        entity_type=file_obj.entity_type.upper() if file_obj.entity_type else 'FILE',
        entity_id=file_obj.sample_id or file_obj.acceptance_act_id or file_obj.contract_id or file_obj.equipment_id or file_obj.standard_id or file_obj.id,
        action='FILE_DOWNLOAD',
        extra_data={'detail': f'Скачан файл: {file_obj.original_name}'}
    )

    # ═══ S3 presigned URL ═══
    from core.services.s3_utils import _get_client, get_bucket

    s3 = _get_client()
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': get_bucket(),
                'Key': file_obj.file_path,
                'ResponseContentType': file_obj.mime_type or 'application/octet-stream',
                'ResponseContentDisposition': f"attachment; filename*=UTF-8''{quote(file_obj.original_name)}",
            },
            ExpiresIn=3600,
        )
    except Exception:
        raise Http404('Файл не найден')

    return redirect(url)


# =============================================================================
# ПРЕВЬЮ / МИНИАТЮРА
# =============================================================================

@login_required
@require_GET
def file_thumbnail(request, file_id):
    """Отдаёт миниатюру файла (через S3 presigned URL)"""
    file_obj = get_object_or_404(File, id=file_id, is_deleted=False)

    if not _can_view_file(request.user, file_obj):
        return JsonResponse({'error': 'Нет доступа'}, status=403)

    from core.services.s3_utils import get_presigned_url

    # Пробуем миниатюру
    if file_obj.thumbnail_path:
        url = get_presigned_url(file_obj.thumbnail_path, expires_in=3600, content_type='image/jpeg')
        if url:
            return redirect(url)

    # Fallback — оригинал (для изображений)
    if file_obj.is_image:
        url = get_presigned_url(file_obj.file_path, expires_in=3600, content_type=file_obj.mime_type)
        if url:
            return redirect(url)

    raise Http404('Миниатюра не найдена')


# =============================================================================
# УДАЛЕНИЕ ФАЙЛА (мягкое)
# =============================================================================

@login_required
@require_POST
def file_delete(request, file_id):
    """Мягкое удаление файла (файл остаётся в S3, помечается как удалённый)"""
    file_obj = get_object_or_404(File, id=file_id, is_deleted=False)

    if not _can_edit_file(request.user, file_obj):
        return JsonResponse({'error': 'Нет прав на удаление'}, status=403)

    file_obj.is_deleted = True
    file_obj.deleted_at = timezone.now()
    file_obj.deleted_by = request.user
    file_obj.save()

    # Аудит
    log_action(
        request,
        entity_type=file_obj.entity_type.upper() if file_obj.entity_type else 'FILE',
        entity_id=file_obj.sample_id or file_obj.acceptance_act_id or file_obj.contract_id or file_obj.equipment_id or file_obj.standard_id or file_obj.id,
        action='FILE_DELETE',
        extra_data={'detail': f'Удалён файл: {file_obj.original_name}'}
    )

    return JsonResponse({'success': True})


# =============================================================================
# ЗАМЕНА ФАЙЛА (версионность)
# =============================================================================

@login_required
@require_POST
def file_replace(request, file_id):
    """
    Замена файла новой версией.
    Старая версия перемещается в _versions/ префикс в S3.
    """
    old_file = get_object_or_404(File, id=file_id, is_deleted=False, current_version=True)

    if not _can_edit_file(request.user, old_file):
        return JsonResponse({'error': 'Нет прав на замену'}, status=403)

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return JsonResponse({'error': 'Файл не выбран'}, status=400)

    if uploaded_file.size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE // (1024 * 1024)
        return JsonResponse({'error': f'Файл слишком большой (макс. {max_mb} МБ)'}, status=400)

    ext = os.path.splitext(uploaded_file.name)[1].lower().lstrip('.')
    if ext not in ALLOWED_EXTENSIONS:
        return JsonResponse({'error': f'Недопустимый формат (.{ext})'}, status=400)

    # 1. Версионирование старого файла в S3
    _move_to_versions(old_file)

    # 2. Помечаем старый как неактуальный
    old_file.current_version = False
    old_file.save()

    # 3. Загружаем новый в S3
    # Берём директорию из пути старого файла (без _versions/)
    old_dir = os.path.dirname(old_file.file_path)
    if '/_versions' in old_dir:
        old_dir = old_dir.rsplit('/_versions', 1)[0]

    safe_name = _safe_filename(uploaded_file.name)
    s3_key = f'{old_dir}/{safe_name}'

    mime, _ = mimetypes.guess_type(uploaded_file.name)

    from core.services.s3_utils import upload_file as s3_upload
    result = s3_upload(uploaded_file, s3_key, content_type=mime)
    if not result:
        return JsonResponse({'error': 'Ошибка загрузки файла'}, status=500)

    # 4. Создаём новую запись
    new_file = File(
        file_path=s3_key,
        original_name=uploaded_file.name,
        file_size=uploaded_file.size,
        mime_type=mime or '',
        category=old_file.category,
        file_type=old_file.file_type,
        sample_id=old_file.sample_id,
        acceptance_act_id=old_file.acceptance_act_id,
        contract_id=old_file.contract_id,
        equipment_id=old_file.equipment_id,
        standard_id=old_file.standard_id,
        owner_id=old_file.owner_id,
        visibility=old_file.visibility,
        version=old_file.version + 1,
        current_version=True,
        replaces=old_file,
        description=old_file.description,
        uploaded_by=request.user,
    )
    new_file.save()

    # Миниатюра
    if new_file.is_image:
        _generate_thumbnail(new_file)

    # Аудит
    log_action(
        request,
        entity_type=new_file.entity_type.upper() if new_file.entity_type else 'FILE',
        entity_id=new_file.sample_id or new_file.acceptance_act_id or new_file.contract_id or new_file.equipment_id or new_file.standard_id or new_file.id,
        action='FILE_REPLACE',
        extra_data={'detail': f'Заменён файл: {old_file.original_name} (v{old_file.version}) → {uploaded_file.name} (v{new_file.version})'}
    )

    return JsonResponse({
        'success': True,
        'file_id': new_file.id,
        'file_name': new_file.original_name,
        'version': new_file.version,
    })


# =============================================================================
# ПОЛУЧЕНИЕ ТИПОВ ФАЙЛОВ ДЛЯ КАТЕГОРИИ (AJAX)
# =============================================================================

@login_required
@require_GET
def api_file_types(request, category):
    """Возвращает доступные типы файлов для категории (для выпадающего списка)"""
    choices = FileType.CHOICES_BY_CATEGORY.get(category, [])
    return JsonResponse({
        'types': [{'value': c[0], 'label': c[1]} for c in choices]
    })


# =============================================================================
# СПИСОК ФАЙЛОВ ДЛЯ СУЩНОСТИ (AJAX)
# =============================================================================

@login_required
@require_GET
def api_entity_files(request, entity_type, entity_id):
    """Возвращает файлы сущности для блока файлов в карточке."""
    data = get_files_for_entity(request.user, entity_type, int(entity_id))

    files_list = []
    for f in data['files']:
        files_list.append({
            'id': f.id,
            'original_name': f.original_name,
            'file_type': f.file_type,
            'file_size': f.size_display,
            'version': f.version,
            'version_count': f.version_count,
            'uploaded_by': str(f.uploaded_by) if f.uploaded_by else '',
            'uploaded_at': f.uploaded_at.strftime('%d.%m.%Y') if f.uploaded_at else '',
            'is_image': f.is_image,
            'is_pdf': f.is_pdf,
            'has_thumbnail': bool(f.thumbnail_path),
            'description': f.description,
        })

    return JsonResponse({
        'files': files_list,
        'hidden_types': list(data['hidden_types']),
        'total_count': data['total_count'],
    })


# =============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================================================================

def _safe_filename(filename):
    """Убирает опасные символы из имени файла"""
    name, ext = os.path.splitext(filename)
    safe = re.sub(r'[^\w\s\-\.\(\)]', '', name, flags=re.UNICODE)
    safe = safe.strip()
    return (safe or 'file') + ext.lower()


def _move_to_versions(file_obj):
    """Копирует файл в _versions/ префикс в S3 и удаляет оригинал."""
    from core.services.s3_utils import _get_client, get_bucket

    old_key = file_obj.file_path
    name = os.path.basename(old_key)
    name_no_ext, ext = os.path.splitext(name)
    date_suffix = file_obj.uploaded_at.strftime('%Y%m%d') if file_obj.uploaded_at else 'unknown'
    versioned_name = f'{name_no_ext}_v{file_obj.version}_{date_suffix}{ext}'

    parent_dir = os.path.dirname(old_key)
    new_key = f'{parent_dir}/_versions/{versioned_name}'

    s3 = _get_client()
    bucket = get_bucket()
    try:
        s3.copy_object(
            Bucket=bucket,
            CopySource={'Bucket': bucket, 'Key': old_key},
            Key=new_key,
        )
        s3.delete_object(Bucket=bucket, Key=old_key)
    except Exception as e:
        print(f'[WARNING] S3 move_to_versions failed: {e}')
        return

    file_obj.file_path = new_key
    file_obj.save()


def _generate_thumbnail(file_obj):
    """Генерирует миниатюру: скачивает из S3, ресайзит, загружает обратно."""
    try:
        from PIL import Image
        from core.services.s3_utils import download_file, upload_bytes

        data = download_file(file_obj.file_path)
        if not data:
            return

        with Image.open(BytesIO(data)) as img:
            img.thumbnail(THUMBNAIL_SIZE)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            buf = BytesIO()
            img.save(buf, 'JPEG', quality=85)
            thumb_bytes = buf.getvalue()

        name_no_ext = os.path.splitext(os.path.basename(file_obj.file_path))[0]
        parent_dir = os.path.dirname(file_obj.file_path)
        thumb_key = f'{parent_dir}/.thumbnails/{name_no_ext}_thumb.jpg'

        upload_bytes(thumb_bytes, thumb_key, content_type='image/jpeg')

        file_obj.thumbnail_path = thumb_key
        file_obj.save()

    except Exception as e:
        print(f'[WARNING] Не удалось создать миниатюру для {file_obj.original_name}: {e}')