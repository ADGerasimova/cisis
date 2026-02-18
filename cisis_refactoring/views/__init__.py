"""
Views разделены на модули по функциональности.

Этот файл позволяет импортировать все view-функции как раньше:
    from core.views import manage_permissions, journal_samples
"""

# Управление правами
from .permissions_views import manage_permissions

# Работа с образцами
from .sample_views import (
    workspace_home,
    journal_samples,
    sample_detail,
    sample_create,
)

# Проверка регистрации и протоколов
from .verification_views import (
    verify_sample,
    verify_protocol,
)

# Работа с файлами
from .file_views import (
    upload_sample_file,
    download_sample_file,
    view_sample_file,
    delete_sample_file,
)

# API эндпоинты
from .api_views import (
    get_client_contracts,
)


__all__ = [
    # Управление правами
    'manage_permissions',
    
    # Образцы
    'workspace_home',
    'journal_samples',
    'sample_detail',
    'sample_create',
    
    # Проверка
    'verify_sample',
    'verify_protocol',
    
    # Файлы
    'upload_sample_file',
    'download_sample_file',
    'view_sample_file',
    'delete_sample_file',
    
    # API
    'get_client_contracts',
]
