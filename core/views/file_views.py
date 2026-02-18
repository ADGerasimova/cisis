from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse
from django.core.files.storage import default_storage
from django.conf import settings
import os

from core.models import Sample, SampleFile
from core.permissions import PermissionChecker

@login_required
def upload_sample_file(request, sample_id):
    """Загрузка файла для образца"""

    if request.method != 'POST':
        return redirect('sample_detail', sample_id=sample_id)

    # Получаем образец
    sample = get_object_or_404(Sample, id=sample_id)

    # Проверяем права на загрузку файлов
    if not PermissionChecker.can_edit(request.user, 'SAMPLES', 'files_path'):
        messages.error(request, 'У вас нет прав на загрузку файлов')
        return redirect('sample_detail', sample_id=sample_id)

    # Проверка доступа к образцу по лаборатории
    # Администраторы и руководство видят ВСЕ образцы — пропускаем проверку
    if request.user.role not in [
        'CLIENT_MANAGER', 'CLIENT_DEPT_HEAD',
        'QMS_HEAD', 'QMS_ADMIN', 'METROLOGIST',
        'SYSADMIN', 'CTO', 'CEO', 'WORKSHOP'
    ]:
        # Остальные роли работают только с образцами своей лаборатории
        if sample.laboratory != request.user.laboratory:
            messages.error(request, 'У вас нет доступа к этому образцу')
            return redirect('sample_detail', sample_id=sample_id)

    # Получаем файл из формы
    uploaded_file = request.FILES.get('file')
    description = request.POST.get('description', '').strip()

    if not uploaded_file:
        messages.error(request, 'Файл не выбран')
        return redirect('sample_detail', sample_id=sample_id)

    # Проверяем расширение
    if hasattr(settings, 'ALLOWED_FILE_EXTENSIONS'):
        file_ext = os.path.splitext(uploaded_file.name)[1].lower()
        if file_ext not in settings.ALLOWED_FILE_EXTENSIONS:
            messages.error(request, f'Недопустимый тип файла: {file_ext}')
            return redirect('sample_detail', sample_id=sample_id)

    # Проверяем размер
    max_size = getattr(settings, 'FILE_UPLOAD_MAX_MEMORY_SIZE', 1073741824)
    if uploaded_file.size > max_size:
        size_mb = max_size / (1024 * 1024)
        messages.error(request, f'Файл слишком большой. Максимальный размер: {size_mb:.0f} МБ')
        return redirect('sample_detail', sample_id=sample_id)

    try:
        # Генерируем путь для сохранения файла
        year = sample.registration_date.year
        folder_path = os.path.join(
            sample.laboratory.code_display,
            str(year),
            sample.cipher
        )

        # Создаём папку
        full_folder_path = os.path.join(settings.MEDIA_ROOT, folder_path)
        os.makedirs(full_folder_path, exist_ok=True)

        # Генерируем уникальное имя файла
        base_name = uploaded_file.name
        file_name = base_name
        counter = 1

        while os.path.exists(os.path.join(full_folder_path, file_name)):
            name, ext = os.path.splitext(base_name)
            file_name = f"{name}_{counter}{ext}"
            counter += 1

        file_path = os.path.join(folder_path, file_name)

        # Сохраняем файл на диск
        full_file_path = os.path.join(settings.MEDIA_ROOT, file_path)
        with open(full_file_path, 'wb+') as destination:
            for chunk in uploaded_file.chunks():
                destination.write(chunk)

        # Создаём запись в БД
        sample_file = SampleFile.objects.create(
            sample=sample,
            file=file_path,
            original_filename=uploaded_file.name,
            file_size=uploaded_file.size,
            uploaded_by=request.user,
            description=description
        )

        messages.success(request, f'Файл "{uploaded_file.name}" успешно загружен')

    except Exception as e:
        messages.error(request, f'Ошибка при загрузке файла: {str(e)}')

    return redirect('sample_detail', sample_id=sample_id)

@login_required
def download_sample_file(request, file_id):
    """Скачивание файла образца"""

    sample_file = get_object_or_404(SampleFile, id=file_id)
    sample = sample_file.sample

    # Проверяем доступ к журналу
    if request.user.role not in [
        'CLIENT_MANAGER', 'CLIENT_DEPT_HEAD',
        'QMS_HEAD', 'QMS_ADMIN', 'METROLOGIST',
        'SYSADMIN', 'CTO', 'CEO' 'WORKSHOP'
    ]:
        if sample.laboratory != request.user.laboratory:
            messages.error(request, 'У вас нет доступа к этому файлу')
            return redirect('workspace_home')

    # Полный путь к файлу
    file_path = os.path.join(settings.MEDIA_ROOT, sample_file.file.name)

    if not os.path.exists(file_path):
        raise Http404('Файл не найден на диске')

    # Отправляем файл
    try:
        response = FileResponse(open(file_path, 'rb'))
        response['Content-Disposition'] = f'attachment; filename="{sample_file.original_filename}"'
        return response
    except Exception as e:
        messages.error(request, f'Ошибка при скачивании: {str(e)}')
        return redirect('sample_detail', sample_id=sample.id)

@login_required
def view_sample_file(request, file_id):
    """Просмотр файла в браузере (для изображений и PDF)"""

    sample_file = get_object_or_404(SampleFile, id=file_id)
    sample = sample_file.sample

    # Проверяем доступ
    if not PermissionChecker.has_journal_access(request.user, 'SAMPLES'):
        messages.error(request, 'У вас нет доступа к журналу образцов')
        return redirect('workspace_home')

    # Проверка доступа к образцу по лаборатории
    if request.user.role not in [
        'CLIENT_MANAGER', 'CLIENT_DEPT_HEAD',
        'QMS_HEAD', 'QMS_ADMIN', 'METROLOGIST',
        'SYSADMIN', 'CTO', 'CEO', 'WORKSHOP'
    ]:
        if sample.laboratory != request.user.laboratory:
            messages.error(request, 'У вас нет доступа к этому файлу')
            return redirect('workspace_home')

    # Полный путь к файлу
    file_path = os.path.join(settings.MEDIA_ROOT, sample_file.file.name)

    if not os.path.exists(file_path):
        raise Http404('Файл не найден на диске')

    # Определяем MIME-type
    content_type = 'application/octet-stream'
    ext = sample_file.get_file_extension()

    mime_types = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
    }

    content_type = mime_types.get(ext, content_type)

    try:
        response = FileResponse(open(file_path, 'rb'), content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{sample_file.original_filename}"'
        return response
    except Exception as e:
        messages.error(request, f'Ошибка при просмотре: {str(e)}')
        return redirect('sample_detail', sample_id=sample.id)

@login_required
def delete_sample_file(request, file_id):
    """Удаление файла образца"""

    if request.method != 'POST':
        return redirect('workspace_home')

    sample_file = get_object_or_404(SampleFile, id=file_id)
    sample = sample_file.sample

    # Проверяем права на удаление
    if not PermissionChecker.can_edit(request.user, 'SAMPLES', 'files_path'):
        messages.error(request, 'У вас нет прав на удаление файлов')
        return redirect('sample_detail', sample_id=sample.id)

    # Проверка доступа к образцу по лаборатории
    if request.user.role not in [
        'CLIENT_MANAGER', 'CLIENT_DEPT_HEAD',
        'QMS_HEAD', 'QMS_ADMIN', 'METROLOGIST',
        'SYSADMIN', 'CTO', 'CEO'
    ]:
        if sample.laboratory != request.user.laboratory:
            messages.error(request, 'У вас нет доступа к этому образцу')
            return redirect('sample_detail', sample_id=sample.id)

    try:
        # Удаляем физический файл
        file_path = os.path.join(settings.MEDIA_ROOT, sample_file.file.name)
        if os.path.exists(file_path):
            os.remove(file_path)

        filename = sample_file.original_filename

        # Удаляем запись из БД
        sample_file.delete()

        messages.success(request, f'Файл "{filename}" успешно удалён')

    except Exception as e:
        messages.error(request, f'Ошибка при удалении файла: {str(e)}')

    return redirect('sample_detail', sample_id=sample.id)
