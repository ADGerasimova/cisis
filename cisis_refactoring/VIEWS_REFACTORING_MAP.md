# КАРТА РЕФАКТОРИНГА VIEWS.PY

## Оригинальный файл: views.py (2016 строк)

Этот документ показывает какой код из оригинального `views.py` нужно перенести в какой новый файл.

---

## 📁 views/permissions_views.py
**Назначение:** Управление правами доступа

**Функции для переноса:**
- `manage_permissions(request)` - строки ~30-236

**Импорты:**
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction

from core.models import (
    User, Journal, JournalColumn, RolePermission,
    UserPermissionOverride, PermissionsLog, UserRole, AccessLevel,
)
from core.permissions import PermissionChecker
```

---

## 📁 views/sample_views.py
**Назначение:** Журнал образцов, создание, детали

**Функции для переноса:**
- `workspace_home(request)` - строки ~238-245
- `journal_samples(request)` - строки ~247-570
- `sample_detail(request, sample_id)` - строки ~572-1250 (БОЛЬШАЯ ФУНКЦИЯ!)
- `sample_create(request)` - строки ~1415-1620

**Вспомогательные функции:**
- `get_allowed_statuses_for_role(role)` - строки ~1252-1280
- `get_field_info(sample, field_code, user)` - строки ~1282-1320
- `handle_sample_save(request, sample)` - строки ~1322-1380
- `handle_m2m_update(sample, field_code, selected_ids)` - строки ~1382-1413

**Импорты:**
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction, models
from datetime import datetime

from core.models import (
    User, Sample, Laboratory, Client, Contract, 
    Standard, AccreditationArea, Equipment,
    SampleMeasuringInstrument, SampleTestingEquipment, SampleOperator,
    SampleStatus, JournalColumn,
)
from core.permissions import PermissionChecker
```

---

## 📁 views/verification_views.py
**Назначение:** Проверка регистрации образцов и протоколов

**Функции для переноса:**
- `verify_sample(request, sample_id)` - строки ~1730-1850
- `verify_protocol(request, sample_id)` - строки ~1852-2016

**Импорты:**
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from datetime import date

from core.models import Sample, SampleStatus
from core.permissions import PermissionChecker
```

---

## 📁 views/file_views.py
**Назначение:** Загрузка, скачивание, просмотр и удаление файлов образцов

**Функции для переноса:**
- `upload_sample_file(request, sample_id)` - строки ~1622-1670
- `download_sample_file(request, file_id)` - строки ~1672-1685
- `view_sample_file(request, file_id)` - строки ~1687-1700
- `delete_sample_file(request, file_id)` - строки ~1702-1728

**Импорты:**
```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse
from django.core.files.storage import default_storage
from django.conf import settings
import os

from core.models import Sample, SampleFile
from core.permissions import PermissionChecker
```

---

## 📁 views/api_views.py
**Назначение:** API эндпоинты (JSON responses)

**Функции для переноса:**
- `get_client_contracts(request, client_id)` - появляется дважды в файле (строки ~1251 и ~1730)
  - ВАЖНО: Оставьте только одну версию!

**Импорты:**
```python
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

from core.models import Contract
```

---

## 🔧 Порядок выполнения рефакторинга views:

### Шаг 1: Создайте структуру
```bash
cd your_project/core/
mkdir views
touch views/__init__.py
touch views/permissions_views.py
touch views/sample_views.py
touch views/verification_views.py
touch views/file_views.py
touch views/api_views.py
```

### Шаг 2: Скопируйте __init__.py
Используйте готовый файл из `cisis_refactoring/views/__init__.py`

### Шаг 3: Перенесите код построчно
Для каждого файла:
1. Откройте оригинальный `views.py`
2. Найдите указанные строки
3. Скопируйте код функции целиком
4. Вставьте в соответствующий новый файл
5. Добавьте необходимые импорты в начало файла

### Шаг 4: Проверьте импорты
После переноса всех функций убедитесь что:
- Все импорты присутствуют
- Нет дублирующихся импортов
- Все ссылки на модели правильные

### Шаг 5: Обновите urls.py
Замените в `core/urls.py`:
```python
# БЫЛО:
from . import views

urlpatterns = [
    path('permissions/', views.manage_permissions, name='manage_permissions'),
    path('workspace/', views.workspace_home, name='workspace_home'),
    # ...
]

# СТАЛО:
from .views import (
    permissions_views,
    sample_views,
    verification_views,
    file_views,
    api_views,
)

urlpatterns = [
    path('permissions/', permissions_views.manage_permissions, name='manage_permissions'),
    path('workspace/', sample_views.workspace_home, name='workspace_home'),
    path('workspace/samples/', sample_views.journal_samples, name='journal_samples'),
    path('workspace/samples/create/', sample_views.sample_create, name='sample_create'),
    path('workspace/samples/<int:sample_id>/', sample_views.sample_detail, name='sample_detail'),
    path('workspace/samples/<int:sample_id>/verify/', verification_views.verify_sample, name='verify_sample'),
    path('workspace/samples/<int:sample_id>/verify-protocol/', verification_views.verify_protocol, name='verify_protocol'),
    path('workspace/samples/<int:sample_id>/upload/', file_views.upload_sample_file, name='upload_sample_file'),
    path('workspace/files/<int:file_id>/download/', file_views.download_sample_file, name='download_sample_file'),
    path('workspace/files/<int:file_id>/view/', file_views.view_sample_file, name='view_sample_file'),
    path('workspace/files/<int:file_id>/delete/', file_views.delete_sample_file, name='delete_sample_file'),
    path('api/contracts/<int:client_id>/', api_views.get_client_contracts, name='get_client_contracts'),
]
```

### Шаг 6: Тестирование
```bash
# Запустите сервер
python manage.py runserver

# Проверьте что все URL работают:
# - /permissions/
# - /workspace/
# - /workspace/samples/
# - Все остальные маршруты
```

---

## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ:

1. **Дубликат get_client_contracts:**
   - Эта функция встречается дважды в оригинальном файле
   - Сравните обе версии и оставьте более полную
   - Обычно первая версия - это черновик, вторая - рабочая

2. **Большая функция sample_detail:**
   - Это самая большая функция (~680 строк)
   - Переносите её аккуратно, проверяйте отступы
   - После переноса проверьте что все вложенные блоки if/for корректны

3. **Вспомогательные функции:**
   - Функции `get_allowed_statuses_for_role`, `get_field_info`, etc.
   - Должны быть в том же файле что и функции которые их вызывают
   - Обычно их помещают ПЕРЕД основными функциями

4. **Импорты моделей:**
   - После рефакторинга models, импорты остаются прежними:
   - `from core.models import Sample` - работает!
   - Django автоматически найдёт модель в `core/models/__init__.py`

---

## 📊 Статистика:

**Оригинальный views.py:** ~2016 строк

**После разделения:**
- permissions_views.py: ~210 строк
- sample_views.py: ~1100 строк (самый большой)
- verification_views.py: ~180 строк
- file_views.py: ~110 строк
- api_views.py: ~20 строк
- __init__.py: ~65 строк

**Итого:** ~1685 строк (экономия ~330 строк за счёт удаления дублик атов)

---

**Дата:** 2026-02-06
**Автор:** Claude (Anthropic)
