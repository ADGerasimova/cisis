"""
shared_link_views.py — Публичные ссылки для внешнего доступа к файлам и папкам

API (требует авторизации):
  POST /api/fm/share-link/create/                → создать ссылку (file_id или folder_id)
  GET  /api/fm/share-link/list/<type>/<id>/      → список ссылок (type=file|folder)
  POST /api/fm/share-link/deactivate/            → деактивировать ссылку

Публичные (без авторизации):
  GET  /shared/<token>/                          → страница скачивания / список файлов
  POST /shared/<token>/                          → проверка пароля
  GET  /shared/<token>/download/                 → скачать файл
  GET  /shared/<token>/download/<file_id>/       → скачать файл из папки
"""

import json
from django.http import JsonResponse, Http404, FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from urllib.parse import quote

from core.models import File
from core.models.files import PersonalFolder
from core.models.shared_links import SharedLink
from core.services.s3_utils import is_s3_enabled, get_presigned_url


# ═════════════════════════════════════════════════════════════════
# API (авторизованные пользователи)
# ═════════════════════════════════════════════════════════════════

@login_required
@require_POST
def api_create_shared_link(request):
    """
    Создаёт публичную ссылку на файл или папку.
    POST JSON: { file_id? | folder_id?, label?, password?, expires_hours?, max_downloads? }
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Неверный формат'}, status=400)

    file_id = data.get('file_id')
    folder_id = data.get('folder_id')

    if not file_id and not folder_id:
        return JsonResponse({'error': 'file_id или folder_id обязателен'}, status=400)

    file_obj = None
    folder_obj = None

    if file_id:
        try:
            file_obj = File.objects.get(id=int(file_id), is_deleted=False)
        except (ValueError, File.DoesNotExist):
            return JsonResponse({'error': 'Файл не найден'}, status=404)

    if folder_id:
        try:
            folder_obj = PersonalFolder.objects.get(id=int(folder_id))
        except (ValueError, PersonalFolder.DoesNotExist):
            return JsonResponse({'error': 'Папка не найдена'}, status=404)

    # Срок жизни
    expires_at = None
    expires_hours = data.get('expires_hours')
    if expires_hours:
        try:
            expires_at = timezone.now() + timezone.timedelta(hours=int(expires_hours))
        except (ValueError, TypeError):
            pass

    # Лимит скачиваний
    max_downloads = 0
    try:
        max_downloads = int(data.get('max_downloads', 0))
    except (ValueError, TypeError):
        pass

    link = SharedLink(
        file=file_obj,
        folder=folder_obj,
        created_by=request.user,
        label=data.get('label', ''),
        expires_at=expires_at,
        max_downloads=max_downloads,
    )

    password = data.get('password', '')
    if password:
        link.set_password(password)

    link.save()

    url = request.build_absolute_uri(f'/shared/{link.token}/')
    return JsonResponse({
        'success': True,
        'id': link.id,
        'token': link.token,
        'url': url,
        'has_password': bool(link.password_hash),
        'expires_at': link.expires_at.strftime('%d.%m.%Y %H:%M') if link.expires_at else None,
        'max_downloads': link.max_downloads,
    })


@login_required
@require_GET
def api_list_shared_links(request, target_type, target_id):
    """Список публичных ссылок для файла или папки."""
    if target_type == 'file':
        links = SharedLink.objects.filter(file_id=target_id)
    elif target_type == 'folder':
        links = SharedLink.objects.filter(folder_id=target_id)
    else:
        return JsonResponse({'error': 'Неверный тип'}, status=400)

    links = links.order_by('-created_at')
    result = []
    for link in links:
        result.append({
            'id': link.id,
            'token': link.token,
            'url': request.build_absolute_uri(f'/shared/{link.token}/'),
            'label': link.label,
            'has_password': bool(link.password_hash),
            'expires_at': link.expires_at.strftime('%d.%m.%Y %H:%M') if link.expires_at else None,
            'max_downloads': link.max_downloads,
            'download_count': link.download_count,
            'is_active': link.is_active,
            'is_valid': link.is_valid,
            'created_at': link.created_at.strftime('%d.%m.%Y %H:%M') if link.created_at else '',
        })
    return JsonResponse({'links': result})


@login_required
@require_POST
def api_deactivate_shared_link(request):
    """Деактивирует ссылку. POST JSON: { link_id }"""
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Неверный формат'}, status=400)

    try:
        link = SharedLink.objects.get(id=int(data.get('link_id', 0)))
    except (ValueError, SharedLink.DoesNotExist):
        return JsonResponse({'error': 'Ссылка не найдена'}, status=404)

    link.is_active = False
    link.save()
    return JsonResponse({'success': True})


# ═════════════════════════════════════════════════════════════════
# ПУБЛИЧНЫЙ ДОСТУП (без авторизации)
# ═════════════════════════════════════════════════════════════════

def _check_link(request, link):
    """Проверяет валидность и пароль. Возвращает response если нужно прервать, иначе None."""
    if not link.is_active:
        return render(request, 'core/shared_expired.html', {'reason': 'deactivated'})
    if link.is_expired:
        return render(request, 'core/shared_expired.html', {'reason': 'expired'})
    if link.is_download_limit_reached:
        return render(request, 'core/shared_expired.html', {'reason': 'limit'})

    needs_password = bool(link.password_hash)
    password_ok = request.session.get(f'shared_{link.id}_auth', False)

    if needs_password and not password_ok:
        if request.method == 'POST':
            entered = request.POST.get('password', '')
            if link.check_password(entered):
                request.session[f'shared_{link.id}_auth'] = True
                return None
            else:
                return render(request, 'core/shared_password.html', {
                    'token': link.token, 'error': 'Неверный пароль',
                })
        else:
            return render(request, 'core/shared_password.html', {'token': link.token})

    return None


def shared_page(request, token):
    """Публичная страница скачивания файла или просмотра папки."""
    link = get_object_or_404(SharedLink, token=token)

    block = _check_link(request, link)
    if block:
        return block

    # Ссылка на файл
    if link.file_id:
        file_obj = link.file
        if not file_obj or file_obj.is_deleted:
            raise Http404('Файл не найден')
        return render(request, 'core/shared_download.html', {
            'link': link, 'file': file_obj, 'token': token,
        })

    # Ссылка на папку
    if link.folder_id:
        folder = link.folder
        if not folder:
            raise Http404('Папка не найдена')

        files_qs = File.objects.filter(
            personal_folder_id=folder.id, current_version=True, is_deleted=False,
        ).order_by('original_name')

        files = []
        for f in files_qs:
            mime = f.mime_type or ''
            if 'image' in mime:
                icon = '🖼️'
            elif 'pdf' in mime:
                icon = '📕'
            elif 'spreadsheet' in mime or 'excel' in mime:
                icon = '📊'
            elif 'word' in mime or 'msword' in mime:
                icon = '📝'
            else:
                icon = '📄'
            files.append({
                'id': f.id, 'name': f.original_name,
                'size': f.size_display, 'icon': icon,
            })

        return render(request, 'core/shared_folder.html', {
            'link': link, 'folder': folder, 'files': files, 'token': token,
        })

    raise Http404('Ссылка не содержит файла или папки')


def shared_download(request, token, file_id=None):
    """Скачивание файла или всей папки (zip) по публичной ссылке."""
    link = get_object_or_404(SharedLink, token=token)

    if not link.is_valid:
        raise Http404('Ссылка недействительна')

    if link.password_hash and not request.session.get(f'shared_{link.id}_auth', False):
        return redirect(f'/shared/{token}/')

    # Скачать всю папку как ZIP
    if link.folder_id and not file_id:
        return _download_folder_zip(link)

    # Определяем файл
    if link.file_id and not file_id:
        file_obj = link.file
    elif link.folder_id and file_id:
        try:
            file_obj = File.objects.get(
                id=int(file_id), personal_folder_id=link.folder_id,
                current_version=True, is_deleted=False,
            )
        except File.DoesNotExist:
            raise Http404('Файл не найден в папке')
    else:
        raise Http404('Неверные параметры')

    if not file_obj or file_obj.is_deleted:
        raise Http404('Файл не найден')

    link.download_count += 1
    link.save()

    return _serve_file(file_obj)


# ═════════════════════════════════════════════════════════════════
# ВСПОМОГАТЕЛЬНЫЕ
# ═════════════════════════════════════════════════════════════════

def _serve_file(file_obj):
    """Отдаёт файл — через S3 presigned URL или с диска."""
    if is_s3_enabled() and file_obj.file_path:
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
            return redirect(url)
        except Exception:
            raise Http404('Файл не найден в хранилище')
    else:
        import os
        from django.conf import settings
        local_path = os.path.join(settings.MEDIA_ROOT, file_obj.file_path)
        if not os.path.exists(local_path):
            raise Http404('Файл не найден')
        return FileResponse(
            open(local_path, 'rb'),
            as_attachment=True,
            filename=file_obj.original_name,
            content_type=file_obj.mime_type or 'application/octet-stream',
        )


def _download_folder_zip(link):
    """Собирает все файлы папки в ZIP и отдаёт."""
    import os
    import zipfile
    from io import BytesIO
    from django.conf import settings
    from django.http import HttpResponse

    files_qs = File.objects.filter(
        personal_folder_id=link.folder_id,
        current_version=True, is_deleted=False,
    )

    buf = BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files_qs:
            file_data = None
            if is_s3_enabled() and f.file_path:
                from core.services.s3_utils import download_file
                file_data = download_file(f.file_path)
            else:
                local_path = os.path.join(settings.MEDIA_ROOT, f.file_path)
                if os.path.exists(local_path):
                    with open(local_path, 'rb') as fh:
                        file_data = fh.read()

            if file_data:
                zf.writestr(f.original_name, file_data)

    link.download_count += 1
    link.save()

    buf.seek(0)
    folder_name = link.folder.name if link.folder else 'files'
    response = HttpResponse(buf.read(), content_type='application/zip')
    response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(folder_name)}.zip"
    return response