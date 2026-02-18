"""
CISIS — Общие views (главная страница, logout).
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

from core.permissions import PermissionChecker


@login_required
def workspace_home(request):
    """Главная страница рабочего пространства с доступными журналами."""

    if request.user.role == 'SYSADMIN':
        return redirect('admin:index')

    journals_config = [
        {
            'code': 'SAMPLES',
            'name': 'Журнал образцов',
            'icon': '🧪',
            'description': 'Регистрация и учёт образцов для испытаний',
            'url': 'journal_samples',
        },
        {
            'code': 'SAMPLES',
            'name': 'Генератор этикеток',
            'icon': '🏷️',
            'description': 'Печать этикеток для образцов',
            'url': 'labels_page',
            'requires_column': 'labels_access',
        },
    ]

    available_journals = [
        j for j in journals_config
        if PermissionChecker.has_journal_access(request.user, j['code'])
           and (
                   'requires_column' not in j
                   or PermissionChecker.can_view(request.user, j['code'], j['requires_column'])
           )
    ]

    return render(request, 'core/workspace_home.html', {
        'journals': available_journals,
        'user': request.user,
    })


@login_required
def logout_view(request):
    """Выход из системы."""
    logout(request)
    return redirect('/workspace')
