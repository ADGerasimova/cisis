"""
file_manager_views.py — Файловый менеджер v3.45.1

Архитектура:
  - Левая панель: виртуальное дерево (ленивая загрузка)
  - Правая панель: содержимое выбранной папки (папки + файлы)

API:
  GET  /api/fm/tree/?path=...            → contents for path
  POST /api/fm/folder/create/            → create personal folder
  POST /api/fm/folder/rename/            → rename personal folder
  POST /api/fm/folder/delete/            → delete personal folder
  POST /api/fm/assign/                   → assign inbox file to entity
  POST /api/fm/folder/share/             → share folder with user
  POST /api/fm/folder/share/remove/      → remove share
  GET  /api/fm/folder/<id>/shares/       → list shares
  GET  /api/fm/search/?type=...&q=...    → search for assign modal

Путь: core/views/file_manager_views.py

v3.45.1 — Исправления:
  - N+1 запросы → annotate(Count) для всех resolver'ов
  - api_fm_assign: очистка старых FK при привязке, поддержка standard
  - Единообразная сигнатура resolver'ов
  - root_nodes_json содержит has_children
  - Пагинация для больших списков (образцы, заказчики)
"""

import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Count, Q

from core.models import File, Laboratory, Sample, Equipment, Standard, User
from core.models.files import (
    FileCategory, FileType, FileVisibilityRule,
    PersonalFolder, PersonalFolderShare,
)
from core.permissions import PermissionChecker
from core.services.s3_utils import get_presigned_url, is_s3_enabled

# ─── Метки типов файлов ───────────────────────────────────────────
FILE_TYPE_LABELS = {}
for _cat, _choices in FileType.CHOICES_BY_CATEGORY.items():
    for _val, _label in _choices:
        FILE_TYPE_LABELS[_val] = _label


# ═════════════════════════════════════════════════════════════════
# Вспомогательные функции
# ═════════════════════════════════════════════════════════════════

def _forbidden_types(user):
    """Set типов файлов, скрытых от роли пользователя."""
    return set(
        FileVisibilityRule.objects.filter(role=user.role).values_list('file_type', flat=True)
    )


def _file_to_dict(f, forbidden):
    """Сериализует File → dict. Возвращает None если файл скрыт."""
    if forbidden and f.file_type in forbidden:
        return None

    download_url = f'/files/{f.id}/download/'
    if is_s3_enabled() and f.file_path:
        try:
            download_url = get_presigned_url(f.file_path)
        except Exception:
            pass

    mime = f.mime_type or ''
    if 'image' in mime:
        icon = 'image'
    elif 'pdf' in mime:
        icon = 'pdf'
    elif 'spreadsheet' in mime or 'excel' in mime:
        icon = 'xlsx'
    elif 'word' in mime or 'msword' in mime:
        icon = 'docx'
    else:
        icon = 'file'

    return {
        'id': f.id,
        'name': f.original_name,
        'size': f.size_display,
        'file_type': f.file_type,
        'file_type_label': FILE_TYPE_LABELS.get(f.file_type, f.file_type),
        'mime_type': mime,
        'icon': icon,
        'uploaded_by': f.uploaded_by.full_name if f.uploaded_by else '—',
        'uploaded_at': f.uploaded_at.strftime('%d.%m.%Y') if f.uploaded_at else '—',
        'download_url': download_url,
        'category': f.category,
    }


def _access(user):
    """Права пользователя на каждую категорию."""
    return {
        'samples':   PermissionChecker.can_view(user, 'FILES', 'samples_files'),
        'clients':   PermissionChecker.can_view(user, 'CLIENTS', 'access'),
        'equipment': PermissionChecker.can_view(user, 'FILES', 'equipment_files'),
        'standards': PermissionChecker.can_view(user, 'FILES', 'standards_files'),
        'qms':       PermissionChecker.can_view(user, 'FILES', 'qms_files'),
        'inbox':     True,
        'personal':  True,
    }


def _can_edit(user, category):
    return {
        'samples':   PermissionChecker.can_edit(user, 'FILES', 'samples_files'),
        'clients':   PermissionChecker.can_edit(user, 'CLIENTS', 'access'),
        'equipment': PermissionChecker.can_edit(user, 'FILES', 'equipment_files'),
        'standards': PermissionChecker.can_edit(user, 'FILES', 'standards_files'),
        'qms':       PermissionChecker.can_edit(user, 'FILES', 'qms_files'),
        'inbox':     True,
        'personal':  True,
    }.get(category, False)


def _empty(error=None):
    return {
        'folders': [], 'files': [], 'breadcrumbs': [],
        'can_upload': False, 'can_create_folder': False,
        'error': error,
    }


# ═════════════════════════════════════════════════════════════════
# Резолвер путей
# ═════════════════════════════════════════════════════════════════

def _resolve(path, user):
    parts = [p for p in (path or '').strip('/').split('/') if p]
    acc = _access(user)
    forbidden = _forbidden_types(user)

    if not parts:
        return _root(acc)

    root = parts[0]
    rest = parts[1:]

    resolvers = {
        'samples':   (_samples,   'samples'),
        'clients':   (_clients,   'clients'),
        'equipment': (_equipment, 'equipment'),
        'standards': (_standards, 'standards'),
        'qms':       (_qms,       'qms'),
        'inbox':     (_inbox,     'inbox'),
        'personal':  (_personal,  'personal'),
    }

    if root in resolvers:
        func, perm_key = resolvers[root]
        # inbox и personal не проверяют доступ через acc
        if perm_key in ('inbox', 'personal') or acc.get(perm_key, False):
            return func(rest, user, forbidden)

    return _empty('Нет доступа или неизвестный путь')


# ── Корень ────────────────────────────────────────────────────────
_ROOT_DEFS = [
    ('samples',   '🧪', 'Журнал образцов'),
    ('clients',   '👥', 'Заказчики'),
    ('equipment', '🔬', 'Оборудование'),
    ('standards', '📖', 'Стандарты'),
    ('qms',       '📋', 'СМК'),
    ('inbox',     '📥', 'Входящие'),
    ('personal',  '🗂️', 'Личное хранилище'),
]


def _root(acc):
    folders = [
        {'path': p, 'label': lb, 'icon': ic, 'has_children': True, 'meta': ''}
        for p, ic, lb in _ROOT_DEFS if acc.get(p, True)
    ]
    return {
        'breadcrumbs': [], 'folders': folders, 'files': [],
        'can_upload': False, 'can_create_folder': False, 'current_path': '',
    }


# ── Образцы ───────────────────────────────────────────────────────
def _samples(parts, user, forbidden):
    if not parts:
        labs = Laboratory.objects.filter(
            department_type='LAB', is_active=True
        ).order_by('code_display')

        # Одним запросом: сколько файлов у образцов каждой лаборатории
        lab_file_counts = dict(
            File.objects.filter(
                category=FileCategory.SAMPLE,
                sample__laboratory__in=labs,
                current_version=True,
            ).values_list('sample__laboratory_id').annotate(cnt=Count('id'))
        )

        folders = []
        for lab in labs:
            cnt = lab_file_counts.get(lab.id, 0)
            folders.append({
                'path': f'samples/{lab.code}',
                'label': lab.code_display,
                'icon': '🏭',
                'has_children': True,
                'meta': f'{cnt} фай.' if cnt else '',
            })
        return {
            'breadcrumbs': [{'label': 'Журнал образцов', 'path': 'samples'}],
            'folders': folders, 'files': [],
            'can_upload': False, 'can_create_folder': False, 'current_path': 'samples',
        }

    lab_code = parts[0]
    try:
        lab = Laboratory.objects.get(code=lab_code, department_type='LAB')
    except Laboratory.DoesNotExist:
        return _empty(f'Лаборатория {lab_code} не найдена')

    base_crumbs = [
        {'label': 'Журнал образцов', 'path': 'samples'},
        {'label': lab.code_display, 'path': f'samples/{lab_code}'},
    ]

    if len(parts) == 1:
        # Annotate: кол-во файлов на каждый образец — один запрос
        samples = (
            Sample.objects.filter(laboratory=lab)
            .annotate(file_count=Count(
                'files', filter=Q(files__current_version=True)
            ))
            .order_by('-created_at')[:500]
        )
        folders = []
        for s in samples:
            label = s.cipher or f'#{s.sequence_number}'
            folders.append({
                'path': f'samples/{lab_code}/{s.id}',
                'label': label,
                'icon': '🧪',
                'has_children': s.file_count > 0,
                'meta': f'{s.file_count} фай.' if s.file_count else '',
            })
        return {
            'breadcrumbs': base_crumbs, 'folders': folders, 'files': [],
            'can_upload': False, 'can_create_folder': False,
            'current_path': f'samples/{lab_code}',
        }

    try:
        sample = Sample.objects.select_related('laboratory', 'client').get(id=int(parts[1]))
    except (ValueError, Sample.DoesNotExist):
        return _empty('Образец не найден')

    files_qs = File.objects.filter(
        sample=sample, current_version=True
    ).select_related('uploaded_by').order_by('file_type', 'uploaded_at')
    files = [d for f in files_qs if (d := _file_to_dict(f, forbidden))]

    label = sample.cipher or f'#{sample.sequence_number}'
    return {
        'breadcrumbs': base_crumbs + [{'label': label, 'path': f'samples/{lab_code}/{sample.id}'}],
        'folders': [], 'files': files,
        'can_upload': _can_edit(user, 'samples'), 'can_create_folder': False,
        'current_path': f'samples/{lab_code}/{sample.id}',
        'upload_context': {'entity_type': 'sample', 'entity_id': sample.id, 'category': 'SAMPLE'},
    }


# ── Заказчики ─────────────────────────────────────────────────────
def _clients(parts, user, forbidden):
    from core.models import Client, Contract, AcceptanceAct

    if not parts:
        clients = Client.objects.filter(is_active=True).order_by('name')[:300]
        folders = [
            {'path': f'clients/{c.id}', 'label': c.name, 'icon': '🏢',
             'has_children': True, 'meta': ''}
            for c in clients
        ]
        return {
            'breadcrumbs': [{'label': 'Заказчики', 'path': 'clients'}],
            'folders': folders, 'files': [],
            'can_upload': False, 'can_create_folder': False, 'current_path': 'clients',
        }

    try:
        client = Client.objects.get(id=int(parts[0]))
    except (ValueError, Client.DoesNotExist):
        return _empty('Заказчик не найден')

    base = [
        {'label': 'Заказчики', 'path': 'clients'},
        {'label': client.name, 'path': f'clients/{client.id}'},
    ]

    if len(parts) == 1:
        cnt_c = File.objects.filter(contract__client=client, current_version=True).count()
        cnt_a = File.objects.filter(acceptance_act__contract__client=client, current_version=True).count()
        folders = [
            {'path': f'clients/{client.id}/contracts', 'label': 'Договоры', 'icon': '📑',
             'has_children': True, 'meta': f'{cnt_c} фай.' if cnt_c else ''},
            {'path': f'clients/{client.id}/acts', 'label': 'Акты ПП', 'icon': '📋',
             'has_children': True, 'meta': f'{cnt_a} фай.' if cnt_a else ''},
        ]
        return {
            'breadcrumbs': base, 'folders': folders, 'files': [],
            'can_upload': False, 'can_create_folder': False,
            'current_path': f'clients/{client.id}',
        }

    sub = parts[1]

    if sub == 'contracts':
        if len(parts) == 2:
            contracts = (
                Contract.objects.filter(client=client)
                .annotate(file_count=Count(
                    'files', filter=Q(files__current_version=True)
                ))
                .order_by('-created_at')
            )
            folders = []
            for c in contracts:
                folders.append({
                    'path': f'clients/{client.id}/contracts/{c.id}',
                    'label': c.number or f'Договор #{c.id}',
                    'icon': '📝', 'has_children': c.file_count > 0,
                    'meta': f'{c.file_count} фай.' if c.file_count else '',
                })
            return {
                'breadcrumbs': base + [{'label': 'Договоры', 'path': f'clients/{client.id}/contracts'}],
                'folders': folders, 'files': [],
                'can_upload': False, 'can_create_folder': False,
                'current_path': f'clients/{client.id}/contracts',
            }

        try:
            contract = Contract.objects.get(id=int(parts[2]), client=client)
        except (ValueError, IndexError, Contract.DoesNotExist):
            return _empty('Договор не найден')

        files_qs = File.objects.filter(
            contract=contract, current_version=True
        ).select_related('uploaded_by').order_by('uploaded_at')
        files = [d for f in files_qs if (d := _file_to_dict(f, forbidden))]
        return {
            'breadcrumbs': base + [
                {'label': 'Договоры', 'path': f'clients/{client.id}/contracts'},
                {'label': contract.number or f'Договор #{contract.id}',
                 'path': f'clients/{client.id}/contracts/{contract.id}'},
            ],
            'folders': [], 'files': files,
            'can_upload': _can_edit(user, 'clients'), 'can_create_folder': False,
            'current_path': f'clients/{client.id}/contracts/{contract.id}',
            'upload_context': {'entity_type': 'contract', 'entity_id': contract.id, 'category': 'CLIENT'},
        }

    if sub == 'acts':
        if len(parts) == 2:
            acts = (
                AcceptanceAct.objects.filter(contract__client=client)
                .annotate(file_count=Count(
                    'files', filter=Q(files__current_version=True)
                ))
                .select_related('contract')
                .order_by('-created_at')
            )
            folders = []
            for a in acts:
                folders.append({
                    'path': f'clients/{client.id}/acts/{a.id}',
                    'label': a.doc_number or f'Акт #{a.id}',
                    'icon': '📋', 'has_children': a.file_count > 0,
                    'meta': f'{a.file_count} фай.' if a.file_count else '',
                })
            return {
                'breadcrumbs': base + [{'label': 'Акты ПП', 'path': f'clients/{client.id}/acts'}],
                'folders': folders, 'files': [],
                'can_upload': False, 'can_create_folder': False,
                'current_path': f'clients/{client.id}/acts',
            }

        try:
            act = AcceptanceAct.objects.get(id=int(parts[2]), contract__client=client)
        except (ValueError, IndexError, AcceptanceAct.DoesNotExist):
            return _empty('Акт не найден')

        files_qs = File.objects.filter(
            acceptance_act=act, current_version=True
        ).select_related('uploaded_by').order_by('uploaded_at')
        files = [d for f in files_qs if (d := _file_to_dict(f, forbidden))]
        return {
            'breadcrumbs': base + [
                {'label': 'Акты ПП', 'path': f'clients/{client.id}/acts'},
                {'label': act.doc_number or f'Акт #{act.id}',
                 'path': f'clients/{client.id}/acts/{act.id}'},
            ],
            'folders': [], 'files': files,
            'can_upload': _can_edit(user, 'clients'), 'can_create_folder': False,
            'current_path': f'clients/{client.id}/acts/{act.id}',
            'upload_context': {'entity_type': 'acceptance_act', 'entity_id': act.id, 'category': 'CLIENT'},
        }

    return _empty('Неизвестный путь')


# ── Оборудование ─────────────────────────────────────────────────
def _equipment(parts, user, forbidden):
    if not parts:
        equips = (
            Equipment.objects.filter(is_active=True)
            .select_related('laboratory')
            .annotate(file_count=Count(
                'files', filter=Q(files__current_version=True)
            ))
            .order_by('name')
        )
        folders = []
        for eq in equips:
            meta_parts = []
            if eq.accounting_number:
                meta_parts.append(eq.accounting_number)
            if eq.file_count:
                meta_parts.append(f'{eq.file_count} фай.')
            folders.append({
                'path': f'equipment/{eq.id}',
                'label': eq.name,
                'icon': '🔬', 'has_children': eq.file_count > 0,
                'meta': ' · '.join(meta_parts),
            })
        return {
            'breadcrumbs': [{'label': 'Оборудование', 'path': 'equipment'}],
            'folders': folders, 'files': [],
            'can_upload': False, 'can_create_folder': False, 'current_path': 'equipment',
        }

    try:
        eq = Equipment.objects.select_related('laboratory').get(id=int(parts[0]))
    except (ValueError, Equipment.DoesNotExist):
        return _empty('Оборудование не найдено')

    files_qs = File.objects.filter(
        equipment=eq, current_version=True
    ).select_related('uploaded_by').order_by('file_type', 'uploaded_at')
    files = [d for f in files_qs if (d := _file_to_dict(f, forbidden))]

    return {
        'breadcrumbs': [
            {'label': 'Оборудование', 'path': 'equipment'},
            {'label': eq.name, 'path': f'equipment/{eq.id}'},
        ],
        'folders': [], 'files': files,
        'can_upload': _can_edit(user, 'equipment'), 'can_create_folder': False,
        'current_path': f'equipment/{eq.id}',
        'upload_context': {'entity_type': 'equipment', 'entity_id': eq.id, 'category': 'EQUIPMENT'},
    }


# ── Стандарты ─────────────────────────────────────────────────────
def _standards(parts, user, forbidden):
    if not parts:
        stds = (
            Standard.objects.filter(is_active=True)
            .annotate(file_count=Count(
                'files', filter=Q(files__current_version=True)
            ))
            .order_by('code')
        )
        folders = []
        for s in stds:
            folders.append({
                'path': f'standards/{s.id}',
                'label': s.code, 'icon': '📖',
                'has_children': s.file_count > 0,
                'meta': f'{s.file_count} фай.' if s.file_count else '',
            })
        return {
            'breadcrumbs': [{'label': 'Стандарты', 'path': 'standards'}],
            'folders': folders, 'files': [],
            'can_upload': False, 'can_create_folder': False, 'current_path': 'standards',
        }

    try:
        std = Standard.objects.get(id=int(parts[0]))
    except (ValueError, Standard.DoesNotExist):
        return _empty('Стандарт не найден')

    files_qs = File.objects.filter(
        standard=std, current_version=True
    ).select_related('uploaded_by').order_by('uploaded_at')
    files = [d for f in files_qs if (d := _file_to_dict(f, forbidden))]

    return {
        'breadcrumbs': [
            {'label': 'Стандарты', 'path': 'standards'},
            {'label': std.code, 'path': f'standards/{std.id}'},
        ],
        'folders': [], 'files': files,
        'can_upload': _can_edit(user, 'standards'), 'can_create_folder': False,
        'current_path': f'standards/{std.id}',
        'upload_context': {'entity_type': 'standard', 'entity_id': std.id, 'category': 'STANDARD'},
    }


# ── СМК ──────────────────────────────────────────────────────────
def _qms(parts, user, forbidden):
    files_qs = File.objects.filter(
        category=FileCategory.QMS, current_version=True
    ).select_related('uploaded_by').order_by('file_type', 'uploaded_at')
    files = [d for f in files_qs if (d := _file_to_dict(f, forbidden))]

    return {
        'breadcrumbs': [{'label': 'СМК', 'path': 'qms'}],
        'folders': [], 'files': files,
        'can_upload': _can_edit(user, 'qms'), 'can_create_folder': False,
        'current_path': 'qms',
        'upload_context': {'entity_type': 'qms', 'entity_id': None, 'category': 'QMS'},
    }


# ── Входящие ─────────────────────────────────────────────────────
def _inbox(parts, user, forbidden):
    files_qs = File.objects.filter(
        category=FileCategory.INBOX, current_version=True
    ).select_related('uploaded_by').order_by('-uploaded_at')
    files = []
    for f in files_qs:
        d = _file_to_dict(f, forbidden)
        if d:
            d['is_inbox'] = True
            files.append(d)

    return {
        'breadcrumbs': [{'label': 'Входящие', 'path': 'inbox'}],
        'folders': [], 'files': files,
        'can_upload': True, 'can_create_folder': False,
        'current_path': 'inbox',
        'upload_context': {'entity_type': 'inbox', 'entity_id': None, 'category': 'INBOX'},
    }


# ── Личное хранилище ─────────────────────────────────────────────
def _personal(parts, user, forbidden):
    if not parts:
        root_folders = (
            PersonalFolder.objects.filter(owner=user, parent__isnull=True)
            .annotate(
                child_count=Count('children'),
                file_count=Count(
                    'files', filter=Q(files__current_version=True)
                ),
            )
            .order_by('name')
        )

        folders = []
        for folder in root_folders:
            folders.append({
                'path': f'personal/f/{folder.id}',
                'label': folder.name, 'icon': '📁',
                'has_children': folder.child_count > 0 or folder.file_count > 0,
                'meta': '',
                'folder_id': folder.id,
                'can_rename': True, 'can_delete': True,
            })

        # Расшаренные с пользователем папки
        shared_cnt = PersonalFolderShare.objects.filter(shared_with=user).count()
        if shared_cnt > 0:
            folders.append({
                'path': 'personal/shared', 'label': 'Расшаренное мне',
                'icon': '👥', 'has_children': True,
                'meta': f'{shared_cnt} пап.',
            })

        # Файлы в корне личного хранилища (без папки)
        files_qs = File.objects.filter(
            category=FileCategory.PERSONAL, owner=user,
            personal_folder__isnull=True, current_version=True,
        ).select_related('uploaded_by').order_by('-uploaded_at')
        files = [d for f in files_qs if (d := _file_to_dict(f, forbidden))]

        return {
            'breadcrumbs': [{'label': 'Личное хранилище', 'path': 'personal'}],
            'folders': folders, 'files': files,
            'can_upload': True, 'can_create_folder': True,
            'current_path': 'personal',
            'upload_context': {'entity_type': 'personal', 'entity_id': None, 'category': 'PERSONAL'},
        }

    # personal/shared
    if parts[0] == 'shared':
        if len(parts) == 1:
            shares = PersonalFolderShare.objects.filter(
                shared_with=user
            ).select_related('folder', 'folder__owner').order_by(
                'folder__owner__last_name', 'folder__name'
            )
            folders = []
            for share in shares:
                fold = share.folder
                folders.append({
                    'path': f'personal/f/{fold.id}',
                    'label': fold.name, 'icon': '📂',
                    'has_children': True,
                    'meta': f'{fold.owner.full_name} · {"👁" if share.access_level == "VIEW" else "✏️"}',
                    'readonly': share.access_level == 'VIEW',
                })
            return {
                'breadcrumbs': [
                    {'label': 'Личное хранилище', 'path': 'personal'},
                    {'label': 'Расшаренное мне', 'path': 'personal/shared'},
                ],
                'folders': folders, 'files': [],
                'can_upload': False, 'can_create_folder': False,
                'current_path': 'personal/shared',
            }

    # personal/f/<folder_id>
    if parts[0] == 'f' and len(parts) >= 2:
        try:
            folder_id = int(parts[1])
        except ValueError:
            return _empty('Неверный путь')

        # Владелец?
        try:
            folder = PersonalFolder.objects.get(id=folder_id, owner=user)
            can_edit = True
            is_shared = False
            shared_by = None
        except PersonalFolder.DoesNotExist:
            # Расшарено пользователю?
            try:
                share = PersonalFolderShare.objects.select_related(
                    'folder', 'folder__owner'
                ).get(folder_id=folder_id, shared_with=user)
                folder = share.folder
                can_edit = share.access_level == 'EDIT'
                is_shared = True
                shared_by = folder.owner
            except PersonalFolderShare.DoesNotExist:
                return _empty('Папка недоступна')

        return _folder_contents(folder, user, forbidden, can_edit, is_shared, shared_by)

    return _empty('Неверный путь')


def _folder_contents(folder, user, forbidden, can_edit, is_shared, shared_by):
    subfolders = (
        PersonalFolder.objects.filter(parent=folder)
        .annotate(
            child_count=Count('children'),
            file_count=Count(
                'files', filter=Q(files__current_version=True)
            ),
        )
        .order_by('name')
    )
    folders = []
    for sf in subfolders:
        folders.append({
            'path': f'personal/f/{sf.id}',
            'label': sf.name, 'icon': '📁',
            'has_children': sf.child_count > 0 or sf.file_count > 0,
            'meta': '',
            'folder_id': sf.id,
            'can_rename': can_edit,
            'can_delete': can_edit,
        })

    files_qs = File.objects.filter(
        personal_folder=folder, current_version=True
    ).select_related('uploaded_by').order_by('-uploaded_at')
    files = [d for f in files_qs if (d := _file_to_dict(f, forbidden))]

    # Хлебные крошки — обход дерева вверх
    ancestors = folder.get_ancestors()
    crumbs_personal = [
        {'label': a.name, 'path': f'personal/f/{a.id}'}
        for a in ancestors
    ]

    prefix = [{'label': 'Личное хранилище', 'path': 'personal'}]
    if is_shared:
        prefix.append({'label': 'Расшаренное мне', 'path': 'personal/shared'})

    return {
        'breadcrumbs': prefix + crumbs_personal,
        'folders': folders, 'files': files,
        'can_upload': can_edit, 'can_create_folder': can_edit,
        'current_path': f'personal/f/{folder.id}',
        'upload_context': {
            'entity_type': 'personal',
            'entity_id': folder.id,
            'category': 'PERSONAL',
        },
        'folder_id': folder.id,
        'can_rename': can_edit and not is_shared,
        'can_delete': can_edit and not is_shared,
        'can_share': not is_shared,
    }


# ═════════════════════════════════════════════════════════════════
# Views
# ═════════════════════════════════════════════════════════════════

@login_required
def file_manager(request):
    """Страница-оболочка файлового менеджера."""
    user = request.user
    acc = _access(user)

    if not any(acc.values()):
        messages.error(request, 'У вас нет доступа к файловому менеджеру')
        return redirect('workspace_home')

    root_nodes = [
        {'path': p, 'icon': ic, 'label': lb, 'has_children': True}
        for p, ic, lb in _ROOT_DEFS
        if acc.get(p, True)
    ]

    return render(request, 'core/file_manager.html', {
        'root_nodes_json': json.dumps(root_nodes, ensure_ascii=False),
        'page_title': 'Файловая система',
    })


@login_required
@require_GET
def api_fm_tree(request):
    """GET /api/fm/tree/?path=..."""
    path = request.GET.get('path', '')
    return JsonResponse(_resolve(path, request.user))


# ═════════════════════════════════════════════════════════════════
# CRUD: Личные папки
# ═════════════════════════════════════════════════════════════════

@login_required
@require_POST
def api_fm_folder_create(request):
    """POST { name, parent_id } → create personal folder."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный запрос'}, status=400)

    name = (data.get('name') or '').strip()
    parent_id = data.get('parent_id')

    if not name:
        return JsonResponse({'error': 'Введите имя папки'}, status=400)
    if len(name) > 200:
        return JsonResponse({'error': 'Имя слишком длинное'}, status=400)

    parent = None
    if parent_id:
        try:
            parent = PersonalFolder.objects.get(id=int(parent_id), owner=request.user)
        except (ValueError, PersonalFolder.DoesNotExist):
            return JsonResponse({'error': 'Родительская папка не найдена'}, status=404)

    if PersonalFolder.objects.filter(owner=request.user, parent=parent, name=name).exists():
        return JsonResponse({'error': 'Папка с таким именем уже существует'}, status=400)

    folder = PersonalFolder.objects.create(owner=request.user, parent=parent, name=name)

    return JsonResponse({
        'ok': True,
        'folder': {
            'id': folder.id,
            'path': f'personal/f/{folder.id}',
            'label': folder.name,
            'icon': '📁',
            'has_children': False,
            'meta': '',
            'folder_id': folder.id,
            'can_rename': True,
            'can_delete': True,
        }
    })


@login_required
@require_POST
def api_fm_folder_rename(request):
    """POST { folder_id, name }."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный запрос'}, status=400)

    name = (data.get('name') or '').strip()
    if not name:
        return JsonResponse({'error': 'Введите имя'}, status=400)

    try:
        folder = PersonalFolder.objects.get(id=int(data.get('folder_id', 0)), owner=request.user)
    except (ValueError, PersonalFolder.DoesNotExist):
        return JsonResponse({'error': 'Папка не найдена'}, status=404)

    if PersonalFolder.objects.filter(
        owner=request.user, parent=folder.parent, name=name
    ).exclude(id=folder.id).exists():
        return JsonResponse({'error': 'Папка с таким именем уже существует'}, status=400)

    folder.name = name
    folder.save(update_fields=['name'])
    return JsonResponse({'ok': True, 'name': name})


@login_required
@require_POST
def api_fm_folder_delete(request):
    """POST { folder_id } — удаляет папку, файлы и подпапки переносит к родителю."""
    try:
        data = json.loads(request.body)
        folder = PersonalFolder.objects.get(id=int(data.get('folder_id', 0)), owner=request.user)
    except (ValueError, TypeError, json.JSONDecodeError, PersonalFolder.DoesNotExist):
        return JsonResponse({'error': 'Папка не найдена'}, status=404)

    # Файлы → родитель
    File.objects.filter(personal_folder=folder).update(personal_folder=folder.parent)
    # Подпапки → родитель
    PersonalFolder.objects.filter(parent=folder).update(parent=folder.parent)
    folder.delete()
    return JsonResponse({'ok': True})


# ═════════════════════════════════════════════════════════════════
# ASSIGN: Привязка файлов из inbox к сущностям
# ═════════════════════════════════════════════════════════════════

# Все FK-поля файла, которые нужно обнулять при перепривязке
_FILE_FK_FIELDS = ('sample', 'equipment', 'standard', 'contract', 'acceptance_act')

# Маппинг: тип сущности → (новая категория, имя FK поля, модель)
_ENTITY_MAP = {
    'sample':         (FileCategory.SAMPLE,    'sample',         'Sample'),
    'equipment':      (FileCategory.EQUIPMENT, 'equipment',      'Equipment'),
    'standard':       (FileCategory.STANDARD,  'standard',       'Standard'),
    'contract':       (FileCategory.CLIENT,    'contract',        'Contract'),
    'acceptance_act': (FileCategory.CLIENT,    'acceptance_act',  'AcceptanceAct'),
}


@login_required
@require_POST
def api_fm_assign(request):
    """
    POST { file_id, entity_type, entity_id }
    Привязывает файл из Входящих к сущности.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный запрос'}, status=400)

    try:
        f = File.objects.get(id=int(data.get('file_id', 0)), category=FileCategory.INBOX)
    except (ValueError, File.DoesNotExist):
        return JsonResponse({'error': 'Файл не найден в Входящих'}, status=404)

    entity_type = data.get('entity_type')
    if entity_type not in _ENTITY_MAP:
        return JsonResponse({'error': 'Неверный тип сущности'}, status=400)

    try:
        entity_id = int(data.get('entity_id', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Неверный ID'}, status=400)

    new_category, fk_name, model_name = _ENTITY_MAP[entity_type]

    # Импорт модели
    from core import models as core_models
    model_cls = getattr(core_models, model_name, None)
    if not model_cls:
        return JsonResponse({'error': 'Модель не найдена'}, status=500)

    try:
        obj = model_cls.objects.get(id=entity_id)
    except model_cls.DoesNotExist:
        return JsonResponse({'error': 'Объект не найден'}, status=404)

    # Очищаем все старые FK
    for field in _FILE_FK_FIELDS:
        setattr(f, field, None)

    # Ставим новый FK
    setattr(f, fk_name, obj)
    f.category = new_category
    if not f.file_type or f.file_type == 'UNSORTED':
        f.file_type = 'OTHER'
    f.save()

    return JsonResponse({'ok': True})


# ═════════════════════════════════════════════════════════════════
# SHARING: Шаринг личных папок
# ═════════════════════════════════════════════════════════════════

@login_required
@require_POST
def api_fm_share_folder(request):
    """POST { folder_id, user_id, access_level }."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный запрос'}, status=400)

    access_level = data.get('access_level', 'VIEW')
    if access_level not in ('VIEW', 'EDIT'):
        return JsonResponse({'error': 'Неверный уровень доступа'}, status=400)

    try:
        folder = PersonalFolder.objects.get(id=int(data.get('folder_id', 0)), owner=request.user)
    except (ValueError, PersonalFolder.DoesNotExist):
        return JsonResponse({'error': 'Папка не найдена'}, status=404)

    try:
        target = User.objects.get(id=int(data.get('user_id', 0)), is_active=True)
    except (ValueError, User.DoesNotExist):
        return JsonResponse({'error': 'Сотрудник не найден'}, status=404)

    if target == request.user:
        return JsonResponse({'error': 'Нельзя поделиться с собой'}, status=400)

    share, created = PersonalFolderShare.objects.get_or_create(
        folder=folder, shared_with=target,
        defaults={'access_level': access_level}
    )
    if not created:
        share.access_level = access_level
        share.save(update_fields=['access_level'])

    return JsonResponse({'ok': True, 'created': created})


@login_required
@require_POST
def api_fm_share_remove(request):
    """POST { folder_id, user_id }."""
    try:
        data = json.loads(request.body)
        folder = PersonalFolder.objects.get(id=int(data.get('folder_id', 0)), owner=request.user)
    except (ValueError, TypeError, json.JSONDecodeError, PersonalFolder.DoesNotExist):
        return JsonResponse({'error': 'Папка не найдена'}, status=404)

    PersonalFolderShare.objects.filter(
        folder=folder, shared_with_id=int(data.get('user_id', 0))
    ).delete()
    return JsonResponse({'ok': True})


@login_required
def api_fm_folder_shares(request, folder_id):
    """GET /api/fm/folder/<id>/shares/ — список шарингов папки."""
    try:
        folder = PersonalFolder.objects.get(id=folder_id, owner=request.user)
    except PersonalFolder.DoesNotExist:
        return JsonResponse({'error': 'Папка не найдена'}, status=404)

    shares = PersonalFolderShare.objects.filter(folder=folder).select_related('shared_with')
    return JsonResponse({
        'shares': [
            {
                'user_id': s.shared_with.id,
                'user_name': s.shared_with.full_name,
                'access_level': s.access_level,
            }
            for s in shares
        ]
    })


# ═════════════════════════════════════════════════════════════════
# SEARCH: Поиск для модала привязки
# ═════════════════════════════════════════════════════════════════

@login_required
@require_GET
def api_fm_search(request):
    """
    GET /api/fm/search/?type=equipment|contract|acceptance_act|standard&q=...
    Используется в модале привязки файла из Входящих.
    """
    entity_type = request.GET.get('type', '')
    q = request.GET.get('q', '').strip()
    if not q or len(q) < 2:
        return JsonResponse({'results': []})

    results = []

    if entity_type == 'equipment':
        qs = Equipment.objects.filter(
            Q(name__icontains=q) | Q(accounting_number__icontains=q),
            is_active=True
        ).order_by('name')[:20]
        results = [{'id': e.id, 'name': e.name,
                     'meta': e.accounting_number or ''} for e in qs]

    elif entity_type == 'standard':
        qs = Standard.objects.filter(
            Q(code__icontains=q) | Q(name__icontains=q),
            is_active=True
        ).order_by('code')[:20]
        results = [{'id': s.id, 'name': s.code,
                     'meta': (s.name or '')[:60]} for s in qs]

    elif entity_type == 'contract':
        from core.models import Contract
        qs = Contract.objects.filter(
            Q(number__icontains=q) | Q(client__name__icontains=q)
        ).select_related('client').order_by('-created_at')[:20]
        results = [{'id': c.id,
                     'name': c.number or f'Договор #{c.id}',
                     'meta': c.client.name if c.client else ''} for c in qs]

    elif entity_type == 'acceptance_act':
        from core.models import AcceptanceAct
        qs = AcceptanceAct.objects.filter(
            Q(doc_number__icontains=q) | Q(contract__client__name__icontains=q)
        ).select_related('contract__client').order_by('-created_at')[:20]
        results = [{'id': a.id,
                     'name': a.doc_number or f'Акт #{a.id}',
                     'meta': a.contract.client.name if a.contract and a.contract.client else ''} for a in qs]

    return JsonResponse({'results': results})


# ═════════════════════════════════════════════════════════════════
# Заглушки для совместимости со старыми URL-маршрутами
# ═════════════════════════════════════════════════════════════════

@login_required
def export_files_xlsx(request):
    """Экспорт списка файлов в XLSX — пока не реализован в новом менеджере."""
    messages.info(request, 'Экспорт будет добавлен в следующей версии')
    return redirect('file_manager')


@login_required
@require_POST
def save_fm_columns(request):
    return JsonResponse({'ok': True})


@login_required
@require_POST
def save_fm_column_widths(request):
    return JsonResponse({'ok': True})