"""
CISIS — View для авторизации через workspace.

Файл: core/views/auth_views.py
⭐ v3.51.0: Защита от brute-force (OWASP A07)
"""

from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.core.cache import cache

from core.models import User

# ⭐ v3.51.0: Brute-force protection
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 900  # 15 минут


def workspace_login(request):
    """Страница входа в систему."""
    if request.user.is_authenticated:
        return redirect('/workspace/')

    error = None
    username = ''

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        next_url = request.POST.get('next', '/workspace/')

        # ⭐ v3.51.0: Проверка блокировки
        cache_key = f'login_attempts_{username}'
        attempts = cache.get(cache_key, 0)
        if attempts >= MAX_LOGIN_ATTEMPTS:
            error = 'Слишком много неудачных попыток. Подождите 15 минут.'
            return render(request, 'core/login.html', {
                'error': error, 'username': username,
                'next': request.GET.get('next', '/workspace/'),
            })

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            user = None

        if user and user.check_password(password):
            if not user.is_active:
                error = 'Учётная запись деактивирована. Обратитесь к администратору.'
            else:
                cache.delete(cache_key)  # Сбросить счётчик при успешном входе
                login(request, user, backend='core.auth_backend.CustomUserBackend')
                return redirect(next_url or '/workspace/')
        else:
            cache.set(cache_key, attempts + 1, timeout=LOCKOUT_SECONDS)
            remaining = MAX_LOGIN_ATTEMPTS - attempts - 1
            if remaining > 0:
                error = f'Неверный логин или пароль. Осталось попыток: {remaining}'
            else:
                error = 'Слишком много неудачных попыток. Подождите 15 минут.'

    return render(request, 'core/login.html', {
        'error': error,
        'username': username,
        'next': request.GET.get('next', '/workspace/'),
    })