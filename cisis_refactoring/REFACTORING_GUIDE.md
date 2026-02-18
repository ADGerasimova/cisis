# РУКОВОДСТВО ПО РЕФАКТОРИНГУ ПРОЕКТА CISIS

## 📋 Обзор

Данный рефакторинг разделяет большие файлы `models.py`, `views.py` и `admin.py` на логические модули для упрощения работы с проектом.

## 🎯 Цели рефакторинга

1. **Уменьшение размера файлов** - избежать загрузки всего контекста в LLM
2. **Логическая группировка** - связанные модели в одном файле
3. **Упрощение навигации** - легко найти нужный код
4. **Масштабируемость** - легко добавлять новые модули

## 📦 Новая структура проекта

```
core/
├── models/
│   ├── __init__.py           # Импортирует всё из модулей
│   ├── base.py              # Базовые справочники
│   ├── sample.py            # Модель Sample + посредники
│   ├── user.py              # Модель User
│   ├── equipment.py         # Equipment + связанные
│   ├── permissions.py       # Система прав доступа
│   ├── logs.py              # Журналы (Climate, Weight, Workshop, Time)
│   └── files.py             # SampleFile
├── views/
│   ├── __init__.py
│   ├── permissions_views.py # Управление правами
│   ├── sample_views.py      # Журнал, регистрация, детали
│   ├── verification_views.py# Проверка регистрации и протоколов
│   ├── file_views.py        # Работа с файлами
│   └── api_views.py         # API эндпоинты
├── admin/
│   ├── __init__.py
│   ├── base_admin.py        # Laboratory, Client, etc.
│   ├── sample_admin.py      # Sample
│   ├── user_admin.py        # User
│   ├── permissions_admin.py # Система прав
│   └── logs_admin.py        # Журналы логов
├── permissions.py           # Остаётся как есть
├── auth_backend.py          # Остаётся как есть
├── urls.py                  # Остаётся как есть
├── apps.py                  # Остаётся как есть
└── tests.py                 # Остаётся как есть
```

## 🔄 Порядок миграции

### Шаг 1: Резервная копия
```bash
# Создайте резервные копии текущих файлов
cp core/models.py core/models.py.backup
cp core/views.py core/views.py.backup
cp core/admin.py core/admin.py.backup
```

### Шаг 2: Создание структуры models/

1. **Создайте папку и файлы:**
```bash
cd your_project/core/
mkdir models
touch models/__init__.py
touch models/base.py
touch models/sample.py
touch models/user.py
touch models/equipment.py
touch models/permissions.py
touch models/logs.py
touch models/files.py
```

2. **Скопируйте содержимое из папки `cisis_refactoring/models/` в `core/models/`**

3. **Удалите старый файл:**
```bash
mv models.py models.py.old  # Переименуйте на всякий случай
```

### Шаг 3: Создание структуры views/

1. **Создайте папку и файлы:**
```bash
mkdir views
touch views/__init__.py
touch views/permissions_views.py
touch views/sample_views.py
touch views/verification_views.py
touch views/file_views.py
touch views/api_views.py
```

2. **Скопируйте содержимое из `cisis_refactoring/views/`**

3. **Удалите старый файл:**
```bash
mv views.py views.py.old
```

### Шаг 4: Создание структуры admin/

1. **Создайте папку и файлы:**
```bash
mkdir admin
touch admin/__init__.py
touch admin/base_admin.py
touch admin/sample_admin.py
touch admin/user_admin.py
touch admin/permissions_admin.py
touch admin/logs_admin.py
```

2. **Скопируйте содержимое из `cisis_refactoring/admin/`**

3. **Удалите старый файл:**
```bash
mv admin.py admin.py.old
```

### Шаг 5: Обновление urls.py

Замените импорты в `core/urls.py`:

```python
# БЫЛО:
from . import views

# СТАЛО:
from .views import permissions_views, sample_views, file_views, api_views

# И обновите ссылки на view-функции:
# БЫЛО:
path('permissions/', views.manage_permissions, name='manage_permissions'),

# СТАЛО:
path('permissions/', permissions_views.manage_permissions, name='manage_permissions'),
```

### Шаг 6: Проверка миграций

```bash
# Проверьте что Django видит модели
python manage.py makemigrations --dry-run

# Если всё ОК, не должно быть новых миграций (модели не изменились)
python manage.py makemigrations

# Должно вывести: "No changes detected"
```

### Шаг 7: Тестирование

```bash
# Запустите сервер
python manage.py runserver

# Проверьте:
# 1. Админка открывается
# 2. Модели видны
# 3. Журнал образцов работает
# 4. Права доступа работают
```

## ✅ Проверочный список

- [ ] Резервные копии созданы
- [ ] Папка `models/` создана и заполнена
- [ ] models.py.old переименован (не удалён!)
- [ ] Папка `views/` создана и заполнена
- [ ] views.py.old переименован
- [ ] Папка `admin/` создана и заполнена
- [ ] admin.py.old переименован
- [ ] urls.py обновлён
- [ ] `makemigrations` не показывает изменений
- [ ] Сервер запускается без ошибок
- [ ] Админка работает
- [ ] Журнал образцов работает

## 🔍 Поиск и устранение неполадок

### Ошибка: "No module named 'core.models'"

**Причина:** Django не видит папку models как модуль

**Решение:** Проверьте, что файл `models/__init__.py` существует и содержит импорты

### Ошибка: "cannot import name 'Sample'"

**Причина:** Импорт не экспортируется из `__init__.py`

**Решение:** Проверьте что в `models/__init__.py` есть строка:
```python
from .sample import Sample
```

### Ошибка при миграциях

**Причина:** Django считает что модели изменились

**Решение:** 
1. Убедитесь что `db_table` и `managed = False` установлены во всех моделях
2. Проверьте что порядок полей совпадает с оригиналом

## 📚 Дополнительные материалы

### Как добавить новую модель?

1. Создайте новый файл в `models/` (например, `reports.py`)
2. Добавьте модель в файл
3. Импортируйте в `models/__init__.py`:
```python
from .reports import Report, ReportTemplate
```
4. Добавьте в `__all__`

### Как добавить новое представление?

1. Добавьте функцию в соответствующий файл `views/`
2. Или создайте новый файл для нового модуля
3. Обновите импорты в `views/__init__.py`
4. Добавьте маршрут в `urls.py`

## 🎉 Преимущества новой структуры

✅ **Меньше контекста для LLM** - работаем только с нужными файлами
✅ **Быстрая навигация** - сразу понятно где искать
✅ **Легче код-ревью** - изменения локализованы
✅ **Проще тестировать** - модули независимы
✅ **Масштабируемость** - легко добавлять новые модули

## 📞 Поддержка

При возникновении проблем:
1. Проверьте резервные копии (models.py.old, views.py.old, admin.py.old)
2. Сравните импорты в __init__.py с оригинальными моделями
3. Проверьте что Django видит все модели через `python manage.py shell`:
```python
from core.models import Sample, User, Laboratory
print(Sample._meta.db_table)  # Должно вывести 'samples'
```

---

**Дата создания:** 2026-02-06
**Версия:** 1.0
**Автор:** Claude (Anthropic)
