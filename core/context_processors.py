"""
CISIS v3.40.0 — Context Processors
"""
from .services.workspace_menu import get_available_journals

def sidebar_menu(request):
    # Выполняется на КАЖДОЙ странице
    if request.user.is_authenticated:
        return {
            'sidebar_journals': get_available_journals(request.user)
        }
    return {'sidebar_journals': []}