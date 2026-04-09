"""
CISIS v3.40.0 — Единый сервис меню
"""
from core.permissions import PermissionChecker
from core.models.feedback import Feedback
from core.models.tasks import Task

# Вынесено из views.py
WORKSPACE_CARDS = [
    {'journal_code': 'SAMPLES', 
     'name': 'Журнал образцов', 
     'icon': '🧪', 'description': 'Регистрация и учёт образцов для испытаний', 
     'url': 'journal_samples', 'url_type': 'name'},
    
    {'journal_code': 'AUDIT_LOG', 
     'requires_column': 'access', 
     'name': 'Журнал аудита', 'icon': '📋', 
     'description': 'Все действия пользователей в системе', 
     'url': 'audit_log', 'url_type': 'name'},
    
    {'journal_code': 'CLIENTS', 
     'requires_column': 'access', 
     'name': 'Заказчики и договоры', 
     'icon': '🏢', 
     'description': 'Управление заказчиками и их договорами', 
     'url': 'directory_clients', 
     'url_type': 'name'},
    
    {'name': 'Файловый менеджер', 
     'icon': '📁', 
     'url': 'file_manager', 
     'description': 'Просмотр и поиск файлов по категориям', 
     'journal_code': 'FILES', 
     'requires_column': 'equipment_files'},

    {'name': 'Справочник стандартов', 'icon': '📚', 'url': 'standards_list', 'description': 'Стандарты и определяемые показатели', 'journal_code': 'SAMPLES', 'requires_column': 'parameters_management'},
    {'code': 'EMPLOYEES', 'name': 'Справочник сотрудников', 'icon': '👩‍🔬', 'description': 'Управление сотрудниками', 'url': 'employees', 'journal_code': 'EMPLOYEES'},
    {'name': 'Аналитика', 'icon': '📊', 'url': 'analytics', 'description': 'Статистика по центру', 'journal_code': 'ANALYTICS', 'requires_column': 'access'},
    {'name': 'Реестр оборудования', 'icon': '🔬', 'url': 'equipment_list', 'description': 'Справочник оборудования лабораторий', 'journal_code': 'EQUIPMENT', 'requires_column': 'access'},
    {'name': 'Журнал климата', 'icon': '🌡️', 'url': 'climate_log', 'description': 'Контроль параметров микроклимата помещений', 'journal_code': 'CLIMATE', 'skip_access_check': True},
    {'name': 'Задачи', 'icon': '📋', 'url': 'task_list', 'description': 'Мои задачи и поручения', 'journal_code': 'TASKS', 'skip_access_check': True},
    {'name': 'Обратная связь', 'icon': '💬', 'url': 'feedback_list', 'description': 'Сообщить о проблеме или предложить улучшение', 'journal_code': 'FEEDBACK', 'skip_access_check': True},
]

def get_available_journals(user):
    """Твоя старая логика, но теперь общая"""
    if not user.is_authenticated:
        return []

    available = []
    for card in WORKSPACE_CARDS:
        if not card.get('skip_access_check'):
            if not PermissionChecker.has_journal_access(user, card['journal_code']):
                continue
            requires_col = card.get('requires_column')
            if requires_col and not PermissionChecker.can_view(user, card['journal_code'], requires_col):
                continue

        item = {
            'name': card['name'],
            'icon': card['icon'],
            'description': card['description'],
            'url': card['url'],
            'url_type': card.get('url_type', 'name'),
            'journal_code': card.get('journal_code'),
        }

        # Бейджи
        if card.get('journal_code') == 'FEEDBACK' and user.role == 'SYSADMIN':
            new_count = Feedback.objects.filter(status='NEW').count()
            if new_count: item['badge_count'] = new_count

        if card.get('journal_code') == 'TASKS':
            open_tasks = Task.objects.filter(assignees__user=user, status__in=['OPEN', 'IN_PROGRESS']).count()
            if open_tasks: item['badge_count'] = open_tasks

        available.append(item)

    if user.role == 'SYSADMIN':
        available.append({
            'name': 'Django Admin', 'icon': '⚙️', 'description': 'Панель администратора',
            'url': '/admin/', 'url_type': 'path', 'journal_code': 'ADMIN'
        })
    
    return available