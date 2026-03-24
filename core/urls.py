"""
URL-маршруты для приложения core

⭐ v3.13.0: sample_views.py разделён на модули.
Импорты идут через core.views.__init__ (обратная совместимость).
"""

from django.urls import path
from .views import (
    permissions_views,
    verification_views,
    file_views,
    api_views,
    label_views,
)
# ⭐ v3.13.0: Новые модули — импортируем напрямую для ясности
from .views.views import workspace_home, logout_view
from .views.sample_views import (
        sample_create, sample_detail,
        unfreeze_registration_block,
        search_protocols, search_standards,
        search_moisture_samples,  # ⭐ v3.15.0
        api_check_operator_accreditation,  # ⭐ v3.28.0
        api_check_operator_accreditation,  # ⭐ v3.28.0
        api_client_invoices_for_sample,  # ⭐ v3.38.0
        api_invoice_acts,  # ⭐ v3.38.0
    )
from .views.journal_views import (
    journal_samples, export_journal_xlsx,
    journal_filter_options, save_column_preferences,
    save_sample_column_widths,  # ⭐ v3.34.0
)
from .views.audit_views import audit_log_view
from .views.bulk_views import bulk_operations
from core.views.directory_views import (
    clients_and_acts_page, client_detail,
    client_create, client_edit, client_toggle,
    contract_create, contract_edit, contract_toggle,
    invoice_create, invoice_edit, invoice_toggle,  # ← новое
    contact_create, contact_edit, contact_delete,
    specification_create, specification_edit, specification_toggle,
    closing_batch_create, closing_batch_edit, closing_batch_delete,
    api_acts_for_batch, api_closing_batch_detail,
)

from .views.act_views import (
    acts_registry, act_create, act_detail, api_contract_acts,
    api_client_invoices, api_contract_specifications,
)

from core.views import parameter_views
from .views.auth_views import workspace_login
from .views.analytics_views import (
    analytics_view, api_laboratories, api_kpi,
    api_monthly_labor, api_laboratory_distribution,
    api_status_distribution, api_daily_registrations,
    api_employee_stats,
)
from core.views import maintenance_views
from core.views import employee_views
from core.views import equipment_views
from core.views import file_manager_views
from core.views import climate_views
from core.views import feedback_views

from core.views import task_views
from core.views import chat_views

urlpatterns = [
    path('workspace/tasks/notifications/', task_views.task_notifications, name='task_notifications'),
    
    path('permissions/', permissions_views.manage_permissions, name='manage_permissions'),
    path('workspace/', workspace_home, name='workspace_home'),
    path('workspace/samples/', journal_samples, name='journal_samples'),
    path('workspace/journal/samples/export/', export_journal_xlsx, name='export_journal_xlsx'),
    path('workspace/samples/filter-options/', journal_filter_options, name='journal_filter_options'),
    path('workspace/samples/save-columns/', save_column_preferences, name='save_column_preferences'),
    path('workspace/samples/save-column-widths/', save_sample_column_widths, name='save_sample_column_widths'),
    path('workspace/samples/bulk/', bulk_operations, name='bulk_operations'),
    path('workspace/samples/create/', sample_create, name='sample_create'),
    path('workspace/samples/<int:sample_id>/', sample_detail, name='sample_detail'),
    # ⭐ v3.12.0: Разморозка блока регистрации
    path('workspace/samples/<int:sample_id>/unfreeze-registration/', unfreeze_registration_block, name='unfreeze_registration'),
    path('workspace/samples/<int:sample_id>/verify/', verification_views.verify_sample, name='verify_sample'),
    path('workspace/samples/<int:sample_id>/verify-protocol/', verification_views.verify_protocol, name='verify_protocol'),
    path('api/search-protocols/', search_protocols, name='search_protocols'),
    path('api/contracts/<int:client_id>/', api_views.get_client_contracts, name='get_client_contracts'),
    path('api/search-standards/', search_standards, name='search_standards'),
    path('api/search-moisture-samples/', search_moisture_samples, name='search_moisture_samples'),  # ⭐ v3.15.0
    path('logout/', logout_view, name='workspace_logout'),
    path('workspace/login/', workspace_login, name='workspace_login'),

    # ⭐ v3.6.0: Генератор этикеток
    path('workspace/labels/', label_views.labels_page, name='labels_page'),
    path('workspace/labels/generate/', label_views.labels_generate, name='labels_generate'),

    path('audit-log/', audit_log_view, name='audit_log'),
    # ⭐ v3.16.0: Справочник заказчиков, договоров и контактов
    path('workspace/clients/', clients_and_acts_page, name='directory_clients'),
    path('workspace/clients/<int:client_id>/invoices/create/', invoice_create, name='invoice_create'),
    path('workspace/invoices/<int:invoice_id>/edit/', invoice_edit, name='invoice_edit'),
    path('workspace/invoices/<int:invoice_id>/toggle/', invoice_toggle, name='invoice_toggle'),
    path('api/invoices/<int:client_id>/', api_client_invoices, name='api_client_invoices'),
    path('api/specifications/<int:contract_id>/', api_contract_specifications, name='api_contract_specifications'),
    path('workspace/contracts/<int:contract_id>/specifications/create/', specification_create, name='specification_create'),
    path('workspace/specifications/<int:spec_id>/edit/', specification_edit, name='specification_edit'),
    path('workspace/specifications/<int:spec_id>/toggle/', specification_toggle, name='specification_toggle'),
    path('workspace/closing-batches/create/', closing_batch_create, name='closing_batch_create'),
    path('workspace/closing-batches/<int:batch_id>/edit/', closing_batch_edit, name='closing_batch_edit'),
    path('workspace/closing-batches/<int:batch_id>/delete/', closing_batch_delete, name='closing_batch_delete'),

    # API:
    path('api/acts-for-batch/', api_acts_for_batch, name='api_acts_for_batch'),
    path('api/closing-batch/<int:batch_id>/', api_closing_batch_detail, name='api_closing_batch_detail'),
    # ⭐ v3.19.0: Акты приёма-передачи
    path('workspace/acceptance-acts/', acts_registry, name='acts_registry'),
    path('workspace/acceptance-acts/create/', act_create, name='act_create'),
    path('workspace/acceptance-acts/<int:act_id>/', act_detail, name='act_detail'),
    path('api/contracts/<int:contract_id>/acts/', api_contract_acts, name='api_contract_acts'),
    # ⭐ v3.38.0: Счета заказчика и акты по счёту (для sample_create)
    path('api/client-invoices-for-sample/<int:client_id>/', api_client_invoices_for_sample, name='api_client_invoices_for_sample'),
    path('api/invoices/<int:invoice_id>/acts/', api_invoice_acts, name='api_invoice_acts'),
    path('workspace/clients/<int:client_id>/detail/', client_detail, name='client_detail'),
    path('workspace/clients/create/', client_create, name='client_create'),
    path('workspace/clients/<int:client_id>/edit/', client_edit, name='client_edit'),
    path('workspace/clients/<int:client_id>/toggle/', client_toggle, name='client_toggle'),
    path('workspace/clients/<int:client_id>/contracts/create/', contract_create, name='contract_create'),
    path('workspace/contracts/<int:contract_id>/edit/', contract_edit, name='contract_edit'),
    path('workspace/contracts/<int:contract_id>/toggle/', contract_toggle, name='contract_toggle'),
    path('workspace/clients/<int:client_id>/contacts/create/', contact_create, name='contact_create'),
    path('workspace/contacts/<int:contact_id>/edit/', contact_edit, name='contact_edit'),
    path('workspace/contacts/<int:contact_id>/delete/', contact_delete, name='contact_delete'),

    # --- Файловая система (v3.21.0) ---
    path('files/upload/', file_views.file_upload, name='file_upload'),
    path('files/<int:file_id>/download/', file_views.file_download, name='file_download'),
    path('files/<int:file_id>/thumbnail/', file_views.file_thumbnail, name='file_thumbnail'),
    path('files/<int:file_id>/delete/', file_views.file_delete, name='file_delete'),
    path('files/<int:file_id>/replace/', file_views.file_replace, name='file_replace'),
    path('api/files/types/<str:category>/', file_views.api_file_types, name='api_file_types'),
    path('api/files/<str:entity_type>/<int:entity_id>/', file_views.api_entity_files, name='api_entity_files'),

    # Справочник стандартов + показатели
    path('workspace/standards/', parameter_views.standards_list, name='standards_list'),
    path('workspace/standards/<int:standard_id>/', parameter_views.standard_detail, name='standard_detail'),

    # AJAX: стандарты
    path('api/standards/save/', parameter_views.api_standard_save, name='api_standard_save'),
    path('api/standards/toggle/', parameter_views.api_standard_toggle, name='api_standard_toggle'),

    # AJAX: показатели (без изменений)
    path('api/parameters/save/', parameter_views.api_parameter_save, name='api_parameter_save'),
    path('api/parameters/delete/', parameter_views.api_parameter_delete, name='api_parameter_delete'),
    path('api/parameters/search/', parameter_views.api_parameter_search, name='api_parameter_search'),
    path('api/parameters/create/', parameter_views.api_parameter_create, name='api_parameter_create'),
    path('api/parameters/reorder/', parameter_views.api_parameter_reorder, name='api_parameter_reorder'),

    path('workspace/files/', file_manager_views.file_manager, name='file_manager'),
    path('workspace/files/export/', file_manager_views.export_files_xlsx, name='export_files_xlsx'),
    path('workspace/files/save-columns/', file_manager_views.save_fm_columns, name='save_fm_columns'),
    path('workspace/files/save-column-widths/', file_manager_views.save_fm_column_widths, name='save_fm_column_widths'),

    # ─── equipment_views (Поверки и аттестации) — 2 новых маршрута ───
    path('workspace/equipment/maintenance-log/save-columns/', equipment_views.save_maintenance_log_columns, name='save_maintenance_log_columns'),
    path('workspace/equipment/maintenance-log/save-column-widths/', equipment_views.save_maintenance_log_column_widths, name='save_maintenance_log_column_widths'),
    # Аналитика 
    path('workspace/analytics/',  analytics_view, name='analytics'),
    # API-эндпоинты аналитики
    path('workspace/analytics/api/laboratories', api_laboratories, name='analytics_api_laboratories'),
    path('workspace/analytics/api/kpi', api_kpi, name='analytics_api_kpi'),
    path('workspace/analytics/api/monthly-labor', api_monthly_labor, name='analytics_api_monthly_labor'),
    path('workspace/analytics/api/laboratory-distribution', api_laboratory_distribution, name='analytics_api_lab_distribution'),
    path('workspace/analytics/api/status-distribution', api_status_distribution, name='analytics_api_status_distribution'),
    path('workspace/analytics/api/daily-registrations',api_daily_registrations, name='analytics_api_daily_registrations'),
    path('workspace/analytics/api/employee-stats', api_employee_stats, name='analytics_api_employee_stats'),
    # Техническое обслуживание
    path('workspace/maintenance/save-columns/', maintenance_views.save_maintenance_columns,
         name='save_maintenance_columns'),
    path('workspace/maintenance/save-column-widths/', maintenance_views.save_maintenance_column_widths,
         name='save_maintenance_column_widths'),
    path('workspace/maintenance/export/', maintenance_views.export_maintenance_xlsx, name='export_maintenance_xlsx'),
    path('workspace/maintenance/', maintenance_views.maintenance_view, name='maintenance'),
    path('workspace/maintenance/<int:plan_id>/', maintenance_views.maintenance_detail_view, name='maintenance_detail'),
    path('workspace/maintenance/<int:plan_id>/edit/', maintenance_views.maintenance_edit_plan, name='maintenance_edit_plan'),
    path('workspace/maintenance/<int:plan_id>/log/<int:log_id>/edit/', maintenance_views.maintenance_edit_log, name='maintenance_edit_log'),

    # Справочник сотрудников
    path('workspace/employees/', employee_views.employees_list, name='employees'),
    path('workspace/employees/add/', employee_views.employee_add, name='employee_add'),
    path('workspace/employees/<int:user_id>/', employee_views.employee_detail, name='employee_detail'),
    path('workspace/employees/<int:user_id>/edit/', employee_views.employee_edit, name='employee_edit'),
    path('workspace/employees/<int:user_id>/deactivate/', employee_views.employee_deactivate, name='employee_deactivate'),
    path('workspace/employees/<int:user_id>/activate/', employee_views.employee_activate, name='employee_activate'),
    path('workspace/employees/<int:user_id>/reset-password/', employee_views.employee_reset_password, name='employee_reset_password'),
    path('workspace/change-password/', employee_views.change_password, name='change_password'),
    path('api/check-username/', employee_views.api_check_username, name='api_check_username'),

    # ⭐ v3.28.0: Матрица ответственности
    path('workspace/employees/<int:user_id>/save-areas/', employee_views.employee_save_areas,
         name='employee_save_areas'),
    path('workspace/responsibility-matrix/', employee_views.responsibility_matrix, name='responsibility_matrix'),
    path('api/responsibility-matrix/save/', employee_views.api_save_matrix, name='api_save_matrix'),

    # ⭐ v3.28.0: Проверка допуска + исключения
    path('api/check-operator-accreditation/', api_check_operator_accreditation,
         name='api_check_operator_accreditation'),
    path('api/standards/toggle-exclusion/', parameter_views.api_standard_toggle_exclusion,
         name='api_standard_toggle_exclusion'),

    # ⭐ v3.35.0: Журнал климата
    path('workspace/climate/', climate_views.climate_log_view, name='climate_log'),
    path('workspace/climate/add/', climate_views.climate_log_add, name='climate_log_add'),
    path('workspace/climate/<int:log_id>/edit/', climate_views.climate_log_edit, name='climate_log_edit'),
    path('workspace/climate/<int:log_id>/delete/', climate_views.climate_log_delete, name='climate_log_delete'),
    path('workspace/climate/quick/', climate_views.climate_quick_add, name='climate_quick_add'),
    path('workspace/climate/quick/submit/', climate_views.climate_quick_submit, name='climate_quick_submit'),
    path('workspace/climate/qr/', climate_views.climate_qr_codes, name='climate_qr_codes'),
    path('workspace/climate/export/', climate_views.export_climate_xlsx, name= 'export_climate_xlsx'),

    # ⭐ v3.35.0: Обратная связь
    path('workspace/feedback/', feedback_views.feedback_list, name='feedback_list'),
    path('workspace/feedback/create/', feedback_views.feedback_create, name='feedback_create'),
    path('workspace/feedback/<int:feedback_id>/update/', feedback_views.feedback_update, name='feedback_update'),
    path('workspace/feedback/<int:feedback_id>/delete/', feedback_views.feedback_delete, name='feedback_delete'),

    # Реестр оборудования ⭐ v3.29.0
    path('workspace/equipment/', equipment_views.equipment_list, name='equipment_list'),
    path('workspace/equipment/save-columns/', equipment_views.save_equipment_columns, name='save_equipment_columns'),
    path('workspace/equipment/save-column-widths/', equipment_views.save_equipment_column_widths, name='save_equipment_column_widths'),
    path('workspace/equipment/filter-options/', equipment_views.equipment_filter_options, name='equipment_filter_options'),
    path('workspace/equipment/export/', equipment_views.export_equipment_xlsx, name='export_equipment_xlsx'),
    path('workspace/equipment/<int:equipment_id>/add-maintenance/', equipment_views.equipment_add_maintenance, name='equipment_add_maintenance'),
    path('workspace/equipment/<int:equipment_id>/maintenance/<int:maintenance_id>/edit/', equipment_views.equipment_edit_maintenance, name='equipment_edit_maintenance'),
    path('workspace/equipment/<int:equipment_id>/maintenance/<int:maintenance_id>/delete/', equipment_views.equipment_delete_maintenance, name='equipment_delete_maintenance'),
    path('workspace/equipment/<int:equipment_id>/edit/', equipment_views.equipment_edit, name='equipment_edit'),
    path('workspace/equipment/maintenance-log/', equipment_views.equipment_maintenance_log, name='equipment_maintenance_log'),
    path('workspace/equipment/maintenance-log/export/', equipment_views.export_maintenance_log_xlsx, name='export_maintenance_log_xlsx'),
    path('workspace/equipment/<int:equipment_id>/', equipment_views.equipment_detail, name='equipment_detail'),
    path('workspace/equipment/<int:equipment_id>/add-plan/', equipment_views.equipment_add_plan, name='equipment_add_plan'),
    path('workspace/equipment/<int:equipment_id>/edit-plan/<int:plan_id>/', equipment_views.equipment_edit_plan, name='equipment_edit_plan'),
    path('workspace/equipment/<int:equipment_id>/delete-plan/<int:plan_id>/', equipment_views.equipment_delete_plan, name='equipment_delete_plan'),
    path('workspace/tasks/', task_views.task_list, name='task_list'),
    path('workspace/tasks/create/', task_views.task_create, name='task_create'),
    path('workspace/tasks/<int:task_id>/status/', task_views.task_update_status, name='task_update_status'),

    # ⭐ v3.40.0: Чат
    path('api/chat/rooms/', chat_views.api_chat_rooms, name='api_chat_rooms'),
    path('api/chat/rooms/<int:room_id>/messages/', chat_views.api_chat_messages, name='api_chat_messages'),
    path('api/chat/rooms/<int:room_id>/mark-read/', chat_views.api_chat_mark_read, name='api_chat_mark_read'),
    path('api/chat/rooms/<int:room_id>/members/', chat_views.api_chat_room_members, name='api_chat_room_members'),
    path('api/chat/rooms/<int:room_id>/leave/', chat_views.api_chat_leave, name='api_chat_leave'),
    path('api/chat/group/', chat_views.api_chat_create_group, name='api_chat_create_group'),
    path('api/chat/direct/', chat_views.api_chat_create_direct, name='api_chat_create_direct'),
    path('api/chat/search-users/', chat_views.api_chat_search_users, name='api_chat_search_users'),
    path('api/chat/unread/', chat_views.api_chat_unread_count, name='api_chat_unread_count'),
    path('api/chat/rooms/<int:room_id>/upload/', chat_views.api_chat_upload_file, name='api_chat_upload_file'),
    path('api/chat/rooms/<int:room_id>/add-member/', chat_views.api_chat_add_member, name='api_chat_add_member'),
    path('api/chat/rooms/<int:room_id>/remove-member/', chat_views.api_chat_remove_member, name='api_chat_remove_member'),
    path('api/chat/rooms/<int:room_id>/delete/', chat_views.api_chat_delete_room, name='api_chat_delete_room'),
    # Аватарки
    path('workspace/employees/<int:user_id>/avatar/upload/', employee_views.avatar_upload, name='avatar_upload'),
    path('workspace/employees/<int:user_id>/avatar/delete/', employee_views.avatar_delete, name='avatar_delete'),
]