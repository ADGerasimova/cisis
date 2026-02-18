# КАРТА РЕФАКТОРИНГА ADMIN.PY

## Оригинальный файл: admin.py (408 строк)

Этот документ показывает какой код из оригинального `admin.py` нужно перенести в какой новый файл.

---

## Структура нового admin/:

```
admin/
├── __init__.py          # Импортирует всё из модулей
├── base_admin.py        # Laboratory, Client, Equipment, Standard и т.д.
├── sample_admin.py      # Sample
├── user_admin.py        # User
├── permissions_admin.py # Journal, RolePermission и т.д.
└── logs_admin.py        # ClimateLog, WeightLog, WorkshopLog, TimeLog
```

---

## 📁 admin/__init__.py

```python
"""
Регистрация всех моделей в Django Admin.
Импортирует классы из разных модулей.
"""

# Не нужно ничего импортировать!
# Регистрация происходит через декораторы @admin.register() в каждом файле

# Этот файл может быть пустым, но для ясности можно добавить комментарий:
# "All admin classes are registered via @admin.register() decorators in their respective modules"
```

---

## 📁 admin/base_admin.py
**Назначение:** Базовые справочники

**Классы для переноса:**

### Inline классы (строки 40-70):
```python
class ClientContactInline(admin.TabularInline):
    # строки 40-42

class ContractInline(admin.TabularInline):
    # строки 45-47

class StandardAccreditationAreaInline(admin.TabularInline):
    # строки 50-52

class EquipmentAccreditationAreaInline(admin.TabularInline):
    # строки 55-57

class EquipmentMaintenanceInline(admin.TabularInline):
    # строки 60-63
```

### ModelAdmin классы:
```python
@admin.register(Laboratory)
class LaboratoryAdmin(admin.ModelAdmin):
    # строки 95-99

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    # строки 102-107

@admin.register(AccreditationArea)
class AccreditationAreaAdmin(admin.ModelAdmin):
    # строки 110-113

@admin.register(Standard)
class StandardAdmin(admin.ModelAdmin):
    # строки 116-121

@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    # строки 124-128

@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    # строки 131-136
```

**Импорты:**
```python
from django.contrib import admin
from core.models import (
    Laboratory,
    Client,
    ClientContact,
    Contract,
    AccreditationArea,
    Standard,
    StandardAccreditationArea,
    Holiday,
    Equipment,
    EquipmentAccreditationArea,
    EquipmentMaintenance,
)
```

---

## 📁 admin/user_admin.py
**Назначение:** Управление пользователями

**Классы для переноса:**

```python
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    # строки 139-219 (ВЕСЬ БЛОК, включая методы и fieldsets)
```

**Импорты:**
```python
from django.contrib import admin
from django.contrib import messages
from core.models import User
```

---

## 📁 admin/sample_admin.py
**Назначение:** Управление образцами

**Классы для переноса:**

### Inline классы:
```python
class SampleMeasuringInstrumentInline(admin.TabularInline):
    # строки 72-74

class SampleTestingEquipmentInline(admin.TabularInline):
    # строки 77-79

class SampleOperatorInline(admin.TabularInline):
    # строки 82-84
```

### ModelAdmin:
```python
@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    # строки 221-357 (ВЕСЬ БОЛЬШОЙ КЛАСС)
```

**Импорты:**
```python
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from datetime import date

from core.models import (
    Sample,
    SampleMeasuringInstrument,
    SampleTestingEquipment,
    SampleOperator,
    JournalColumn,
)
from core.permissions import PermissionChecker
```

---

## 📁 admin/permissions_admin.py
**Назначение:** Система прав доступа

**Классы для переноса:**

### Inline:
```python
class JournalColumnInline(admin.TabularInline):
    # строки 66-69
```

### ModelAdmin:
```python
@admin.register(Journal)
class JournalAdmin(admin.ModelAdmin):
    # строки 360-363

@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    # строки 366-369

@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(admin.ModelAdmin):
    # строки 372-375

@admin.register(PermissionsLog)
class PermissionsLogAdmin(admin.ModelAdmin):
    # строки 378-382
```

**Импорты:**
```python
from django.contrib import admin
from core.models import (
    Journal,
    JournalColumn,
    RolePermission,
    UserPermissionOverride,
    PermissionsLog,
)
```

---

## 📁 admin/logs_admin.py
**Назначение:** Журналы логирования

**Классы для переноса:**

```python
@admin.register(ClimateLog)
class ClimateLogAdmin(admin.ModelAdmin):
    # строки 385-389

@admin.register(WeightLog)
class WeightLogAdmin(admin.ModelAdmin):
    # строки 392-395

@admin.register(WorkshopLog)
class WorkshopLogAdmin(admin.ModelAdmin):
    # строки 398-401

@admin.register(TimeLog)
class TimeLogAdmin(admin.ModelAdmin):
    # строки 404-408
```

**Импорты:**
```python
from django.contrib import admin
from core.models import (
    ClimateLog,
    WeightLog,
    WorkshopLog,
    TimeLog,
)
```

---

## 🔧 Порядок выполнения рефакторинга admin:

### Шаг 1: Создайте структуру
```bash
cd your_project/core/
mkdir admin
touch admin/__init__.py
touch admin/base_admin.py
touch admin/user_admin.py
touch admin/sample_admin.py
touch admin/permissions_admin.py
touch admin/logs_admin.py
```

### Шаг 2: Создайте __init__.py
```python
# admin/__init__.py
"""
All admin classes are registered via @admin.register() decorators
in their respective modules.
"""

# Импортируем все модули чтобы декораторы @admin.register() сработали
from . import base_admin
from . import user_admin
from . import sample_admin
from . import permissions_admin
from . import logs_admin
```

### Шаг 3: Перенесите код
Для каждого файла:
1. Добавьте импорты в начало
2. Скопируйте Inline классы (если есть)
3. Скопируйте ModelAdmin классы с декораторами @admin.register()
4. Убедитесь что отступы сохранились

### Шаг 4: Важные моменты

**Декораторы @admin.register():**
- Они должны быть ПЕРЕД классом
- Регистрация происходит автоматически при импорте модуля
- Поэтому в `admin/__init__.py` мы импортируем все модули

**Inline классы:**
- Должны быть определены ПЕРЕД классом который их использует
- Например, `ClientContactInline` должен быть перед `ClientAdmin`

**Импорт from**:
- После рефакторинга models, импорт остаётся прежним
- `from core.models import Sample` - работает!

### Шаг 5: Переименуйте старый файл
```bash
mv admin.py admin.py.old
```

### Шаг 6: Тестирование
```bash
python manage.py runserver
```

Откройте `/admin/` и проверьте:
- ✅ Все модели видны
- ✅ Inline формы работают
- ✅ Права доступа работают
- ✅ Действия (deactivate_users, activate_users) доступны

---

## ⚠️ ВАЖНЫЕ ЗАМЕЧАНИЯ:

1. **Порядок импортов в __init__.py:**
   - Не важен, т.к. декораторы регистрируют модели независимо
   - Но для читаемости лучше сохранить логический порядок

2. **Inline классы в разных файлах:**
   - `SampleMeasuringInstrumentInline` используется в `SampleAdmin`
   - Они должны быть в одном файле (sample_admin.py)

3. **Двойной импорт admin:**
   - В оригинале есть `from django.contrib import admin` дважды (строки 1 и 30)
   - В новых файлах импортируйте один раз

4. **PermissionChecker:**
   - Используется в `SampleAdmin` и `UserAdmin`
   - Импортируйте в соответствующие файлы

---

## 📊 Статистика:

**Оригинальный admin.py:** ~408 строк

**После разделения:**
- base_admin.py: ~100 строк
- user_admin.py: ~85 строк
- sample_admin.py: ~150 строк
- permissions_admin.py: ~40 строк
- logs_admin.py: ~35 строк
- __init__.py: ~10 строк

**Итого:** ~420 строк (небольшое увеличение за счёт повторяющихся импортов)

---

**Дата:** 2026-02-06
**Автор:** Claude (Anthropic)
