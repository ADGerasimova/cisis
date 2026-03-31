"""
shared_link_views.py — Публичные ссылки для внешнего доступа к файлам

API (требует авторизации):
  POST /api/fm/share-link/create/       → создать ссылку
  GET  /api/fm/share-link/list/<file_id>/ → список ссылок файла
  POST /api/fm/share-link/deactivate/   → деактивировать ссылку

Публичные (без авторизации):
  GET  /shared/<token>/                  → страница скачивания
  POST /shared/<token>/                  → проверка пароля
  GET  /shared/<token>/download/         → скачать файл
"""

import json
from django.http import JsonResponse, Http404, FileResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from urllib.parse import quote

from core.models import File
from core.models.shared_links import SharedLink
from core.services.s3_utils import is_s3_enabled, get_presigned_url


# ═════════════════════════════════════════════════════════════════
# API (авторизованные пользователи)
# ═════════════════════════════════════════════════════════════════

@login_required
@require_POST
def api_create_shared_link(request):
    """
    Создаёт публичную ссылку на файл.
    POST JSON: { file_id, label?, password?, expires_hours?, max_downloads? }
    """
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Неверный формат'}, status=400)

    file_id = data.get('file_id')
    if not file_id:
        return JsonResponse({'error': 'file_id обязателен'}, status=400)

    try:
        file_obj = File.objects.get(id=int(file_id), is_deleted=False)
    except (ValueError, File.DoesNotExist):
        return JsonResponse({'error': 'Файл не найден'}, status=404)

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
        created_by=request.user,
        label=data.get('label', ''),
        expires_at=expires_at,
        max_downloads=max_downloads,
    )

    # Пароль
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
def api_list_shared_links(request, file_id):
    """Список публичных ссылок для файла."""
    links = SharedLink.objects.filter(file_id=file_id).order_by('-created_at')
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

def shared_page(request, token):
    """
    Публичная страница скачивания файла.
    GET — показывает страницу (или форму пароля).
    POST — проверяет пароль.
    """
    link = get_object_or_404(SharedLink, token=token)

    # Проверки валидности
    if not link.is_active:
        return render(request, 'core/shared_expired.html', {'reason': 'deactivated'})
    if link.is_expired:
        return render(request, 'core/shared_expired.html', {'reason': 'expired'})
    if link.is_download_limit_reached:
        return render(request, 'core/shared_expired.html', {'reason': 'limit'})

    file_obj = link.file
    if not file_obj or file_obj.is_deleted:
        raise Http404('Файл не найден')

    # Пароль
    needs_password = bool(link.password_hash)
    password_ok = request.session.get(f'shared_{link.id}_auth', False)

    if needs_password and not password_ok:
        if request.method == 'POST':
            entered = request.POST.get('password', '')
            if link.check_password(entered):
                request.session[f'shared_{link.id}_auth'] = True
                password_ok = True
            else:
                return render(request, 'core/shared_password.html', {
                    'token': token, 'error': 'Неверный пароль',
                })
        else:
            return render(request, 'core/shared_password.html', {'token': token})

    return render(request, 'core/shared_download.html', {
        'link': link,
        'file': file_obj,
        'token': token,
    })


def shared_download(request, token):
    """Скачивание файла по публичной ссылке."""
    link = get_object_or_404(SharedLink, token=token)

    if not link.is_valid:
        raise Http404('Ссылка недействительна')

    # Проверка пароля
    if link.password_hash and not request.session.get(f'shared_{link.id}_auth', False):
        return redirect(f'/shared/{token}/')

    file_obj = link.file
    if not file_obj or file_obj.is_deleted:
        raise Http404('Файл не найден')

    # Увеличиваем счётчик скачиваний
    link.download_count += 1
    link.save()

    # Отдаём файл
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
