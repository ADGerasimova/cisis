# РЕФАКТОРИНГ ПРОЕКТА CISIS - БЫСТРЫЙ СТАРТ

## 🎯 Цель

Разделить большие файлы `models.py`, `views.py` и `admin.py` на логические модули для упрощения работы с LLM и улучшения структуры проекта.

## 📦 Что вы получите

### До рефакторинга:
```
core/
├── models.py     (1200 строк) ← 😰
├── views.py      (2016 строк) ← 😱
├── admin.py      (408 строк)  ← 😓
├── urls.py
└── ...
```

### После рефакторинга:
```
core/
├── models/
│   ├── __init__.py      (120 строк)
│   ├── base.py          (250 строк) ← Лаборатории, Клиенты, Договоры
│   ├── user.py          (180 строк) ← Пользователи
│   ├── equipment.py     (200 строк) ← Оборудование
│   ├── sample.py        (450 строк) ← Образцы ⭐
│   ├── permissions.py   (150 строк) ← Права доступа
│   ├── logs.py          (120 строк) ← Журналы
│   └── files.py         (110 строк) ← Файлы
├── views/
│   ├── __init__.py             (65 строк)
│   ├── permissions_views.py    (210 строк)
│   ├── sample_views.py        (1100 строк) ← Основная работа
│   ├── verification_views.py   (180 строк)
│   ├── file_views.py           (110 строк)
│   └── api_views.py             (20 строк)
├── admin/
│   ├── __init__.py             (10 строк)
│   ├── base_admin.py          (100 строк)
│   ├── user_admin.py           (85 строк)
│   ├── sample_admin.py        (150 строк)
│   ├── permissions_admin.py    (40 строк)
│   └── logs_admin.py           (35 строк)
└── ...
```

## 🚀 Быстрый старт

### 1. Резервные копии (ОБЯЗАТЕЛЬНО!)
```bash
cd your_project/core/
cp models.py models.py.backup
cp views.py views.py.backup
cp admin.py admin.py.backup
```

### 2. Скопируйте готовые модули

**Из папки `cisis_refactoring/` скопируйте:**

#### models/ - ГОТОВО К ИСПОЛЬЗОВАНИЮ ✅
```bash
cp -r cisis_refactoring/models ./
```
Все ссылки между моделями исправлены, миграции не потребуются.

#### views/ - ТРЕБУЕТ ПЕРЕНОСА КОДА ⚠️
```bash
cp -r cisis_refactoring/views ./
```
**ВНИМАНИЕ:** Файлы содержат только структуру и импорты.
Используйте `VIEWS_REFACTORING_MAP.md` для переноса кода из старого `views.py`.

#### admin/ - ТРЕБУЕТ ПЕРЕНОСА КОДА ⚠️
Создайте структуру вручную (см. `ADMIN_REFACTORING_MAP.md`).

### 3. Переименуйте старые файлы
```bash
mv models.py models.py.old
mv views.py views.py.old    # После переноса кода!
mv admin.py admin.py.old    # После переноса кода!
```

### 4. Обновите urls.py

**Было:**
```python
from . import views

urlpatterns = [
    path('permissions/', views.manage_permissions, ...),
    # ...
]
```

**Стало:**
```python
from .views import (
    permissions_views,
    sample_views,
    verification_views,
    file_views,
    api_views,
)

urlpatterns = [
    path('permissions/', permissions_views.manage_permissions, ...),
    path('workspace/', sample_views.workspace_home, ...),
    # ... см. полный пример в VIEWS_REFACTORING_MAP.md
]
```

### 5. Проверка
```bash
# Должно вывести: "No changes detected"
python manage.py makemigrations

# Запуск сервера
python manage.py runserver
```

## 📚 Документация

### Основные руководства:
1. **REFACTORING_GUIDE.md** - Полное руководство по рефакторингу
2. **VIEWS_REFACTORING_MAP.md** - Карта переноса кода views
3. **ADMIN_REFACTORING_MAP.md** - Карта переноса кода admin

### Что готово к использованию:

✅ **models/** - Полностью готово!
- Все модели разделены
- Все ссылки исправлены
- Импорты в `__init__.py` настроены
- Можно копировать как есть

⚠️ **views/** - Требует переноса кода
- Структура создана
- Импорты подготовлены
- Нужно скопировать функции из старого views.py
- См. `VIEWS_REFACTORING_MAP.md`

⚠️ **admin/** - Требует переноса кода
- Структуру нужно создать
- Нужно скопировать классы из старого admin.py
- См. `ADMIN_REFACTORING_MAP.md`

## 🎓 Как работать дальше

### С LLM (Claude, ChatGPT):

**Вместо того чтобы загружать весь models.py:**
```
"Вот мой models.py [1200 строк]"  ❌
```

**Теперь можно:**
```
"Вот модели образцов (models/sample.py) [450 строк]"  ✅
```

Это экономит токены контекста и делает ответы LLM более точными!

### При добавлении новых моделей:

1. Создайте новый файл в `models/` (например, `reports.py`)
2. Добавьте импорты в `models/__init__.py`
3. Готово!

Аналогично для views и admin.

## ⚠️ Важные замечания

1. **Не удаляйте старые файлы!**
   - Переименуйте в `.old`
   - Храните как минимум 2 недели
   - Это ваша страховка

2. **Миграции:**
   - `makemigrations` не должен создавать новых миграций
   - Если создаёт - что-то пошло не так
   - Сравните `db_table` и `managed` в моделях

3. **Ссылки между моделями:**
   - Используйте строки: `'User'`, `'Sample'`
   - НЕ используйте `'user.User'` или `'sample.Sample'`
   - Django сам найдёт модель в приложении

4. **Импорты остаются прежними:**
   ```python
   from core.models import Sample  # Работает как раньше!
   from core.views import journal_samples  # Тоже работает!
   ```

## 🆘 Проблемы?

### Ошибка: "No module named 'core.models'"
→ Проверьте что `models/__init__.py` существует

### Ошибка: "cannot import name 'Sample'"
→ Проверьте что в `models/__init__.py` есть `from .sample import Sample`

### Ошибка при миграциях
→ Убедитесь что все модели имеют `managed = False` (кроме SampleFile)

## 📊 Статистика

**Экономия контекста для LLM:**
- Вместо 1200 строк models.py → 450 строк sample.py (63% экономия)
- Вместо 2016 строк views.py → 1100 строк sample_views.py (45% экономия)

**Время на поиск кода:**
- До: "Где тут модель Sample?" → Ctrl+F по 1200 строкам
- После: Открыть `models/sample.py` → Сразу видно всё

## 🎉 Готово!

После рефакторинга вы сможете:
- ✅ Работать с нужными файлами без загрузки всего проекта в LLM
- ✅ Быстро находить нужный код
- ✅ Легко добавлять новые модули
- ✅ Делать код-ревью проще (изменения локализованы)

---

**Дата:** 2026-02-06  
**Версия:** 1.0  
**Автор:** Claude (Anthropic)

**Следующий шаг:** Откройте `REFACTORING_GUIDE.md` для детальных инструкций!
