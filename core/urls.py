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
        search_uzk_samples,  # ⭐ v3.64.0
        api_check_operator_accreditation,  # ⭐ v3.28.0
        api_validate_draft_ready,  # ⭐ v3.84.0
        api_validate_sample_fk_change,  # ⭐ v3.85.0
        api_client_invoices_for_sample,  # ⭐ v3.38.0
        api_invoice_acts,  # ⭐ v3.38.0
        api_standard_parameters,  # ⭐ v3.43.0
        api_protocol_sample_data,
        api_sample_field_changes,
        api_sample_schedule_calc,


    )
from .views.journal_views import (
    journal_samples, export_journal_xlsx,
    journal_filter_options, save_column_preferences,
    save_sample_column_widths,  # ⭐ v3.34.0
    save_filter_preferences,  # ⭐ v3.81.0
    release_drafts, delete_draft,  # ⭐ v3.89.0
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
    api_client_acts,  api_act_samples
)

from core.views import parameter_views
from core.views import protocol_template_views  # ⭐ v3.44.0
from core.views.protocol_template_views import generate_protocol_template  # ⭐ v3.44.0
from .views.auth_views import workspace_login
from .views.analytics_views import (
    # Страницы
    analytics_view,
    analytics_employees_view,
    analytics_employee_detail_view,
    # Справочники
    api_laboratories,
    api_test_types,
    # Блок 1: KPI
    api_kpi,
    # Блок 2: Воронка
    api_funnel,
    api_stage_durations,
    # Блок 3: Динамика
    api_daily_dynamics,
    api_monthly_labor,
    # Блок 4: Срезы
    api_laboratory_distribution,
    api_status_distribution,
    api_test_type_distribution,
    api_accreditation_distribution,
    api_report_type_distribution,
    # Блок 5: Топы
    api_top_clients,
    api_top_standards,
    # Блок 6: Риски
    api_risk_stuck_samples,
    api_risk_equipment_expiring,
    api_risk_replacement_protocols,
    # Блок 7: Drill-down
    api_samples_drill_down,
    # Блок 8: Производительность сотрудников
    api_employees_overview,
    api_employees_leaderboard,
    api_employees_heatmap,
    api_employee_detail,
)

from core.views.test_report_views import (
     api_get_template_config,
     api_get_template_versions,
     api_save_template_config,
     api_delete_template_config,
     api_preview_template_config,
     api_upload_report_template,
     api_report_template_list,
     api_report_template_detail,
     api_get_report_form,
     api_save_test_report,
     api_calculate_report,
     api_export_test_report_xlsx,
     api_export_test_report_xlsx_by_sample,
)
from core.views import maintenance_views
from core.views import employee_views
from core.views import equipment_views
from core.views import file_manager_views
from core.views import climate_views
from core.views import feedback_views

from core.views import task_views
from core.views import equipment_calendar_views
from core.views import chat_views
from django.views.generic import RedirectView
from core.views import shared_link_views
from core.views import test_report_views

from core.views.maintenance_notice_views import (
    api_maintenance_notify,
    api_maintenance_cancel,
    api_maintenance_status,
)

urlpatterns = [
    path('workspace/tasks/notifications/', task_views.task_notifications, name='task_notifications'),
    path('workspace/equipment/calendar/', equipment_calendar_views.equipment_calendar, name='equipment_calendar'),
    path('workspace/equipment/calendar/events/', equipment_calendar_views.equipment_calendar_events, name='equipment_calendar_events'),

    path('permissions/', permissions_views.manage_permissions, name='manage_permissions'),
    path('workspace/', workspace_home, name='workspace_home'),
    path('workspace/samples/', journal_samples, name='journal_samples'),
    path('workspace/journal/samples/export/', export_journal_xlsx, name='export_journal_xlsx'),
    path('workspace/samples/filter-options/', journal_filter_options, name='journal_filter_options'),
    path('workspace/samples/save-columns/', save_column_preferences, name='save_column_preferences'),
    path('workspace/samples/save-filters/', save_filter_preferences, name='save_filter_preferences'),  # ⭐ v3.81.0
    path('workspace/samples/save-column-widths/', save_sample_column_widths, name='save_sample_column_widths'),
    path('workspace/samples/bulk/', bulk_operations, name='bulk_operations'),
    path('workspace/samples/create/', sample_create, name='sample_create'),
    # ⭐ v3.89.0: Черновики регистрации
    path('workspace/samples/drafts/release/', release_drafts, name='release_drafts'),
    path('workspace/samples/drafts/<int:draft_id>/delete/', delete_draft, name='delete_draft'),
    path('workspace/samples/<int:sample_id>/', sample_detail, name='sample_detail'),
    path('api/protocol-sample-data/', api_protocol_sample_data, name='api_protocol_sample_data'),
    path('api/samples/<int:sample_id>/field-changes/', api_sample_field_changes, name='api_sample_field_changes'),
    path('api/sample-schedule-calc/', api_sample_schedule_calc, name='api_sample_schedule_calc'),
    # ⭐ v3.12.0: Разморозка блока регистрации
    path('workspace/samples/<int:sample_id>/unfreeze-registration/', unfreeze_registration_block, name='unfreeze_registration'),
    path('workspace/samples/<int:sample_id>/protocol-template/', generate_protocol_template, name='generate_protocol_template'),  # ⭐ v3.44.0
    path('workspace/samples/<int:sample_id>/verify/', verification_views.verify_sample, name='verify_sample'),
    path('workspace/samples/<int:sample_id>/verify-protocol/', verification_views.verify_protocol, name='verify_protocol'),
    path('workspace/samples/<int:sample_id>/protocol-template/', protocol_template_views.generate_protocol_template, name='generate_protocol_template'),  # ⭐ v3.44.0
    path('api/search-protocols/', search_protocols, name='search_protocols'),
    path('api/contracts/<int:client_id>/', api_views.get_client_contracts, name='get_client_contracts'),
    path('api/act-samples/<int:act_id>/', api_act_samples, name='api_act_samples'),
    path('api/search-standards/', search_standards, name='search_standards'),
    path('api/standard-parameters/', api_standard_parameters, name='api_standard_parameters'),  # ⭐ v3.43.0
    path('api/search-moisture-samples/', search_moisture_samples, name='search_moisture_samples'),  # ⭐ v3.15.0
    path('api/search-uzk-samples/', search_uzk_samples, name='search_uzk_samples'),  # ⭐ v3.64.0
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
    path('api/clients/<int:client_id>/acts/', api_client_acts, name='api_client_acts'),  # ⭐ v3.56.0
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

    # --- Файловый менеджер: страница ---
    path('workspace/files/', file_manager_views.file_manager, name='file_manager'),

    # --- Файловый менеджер: API дерева ---
    path('api/fm/tree/', file_manager_views.api_fm_tree, name='api_fm_tree'),

    # --- Личные папки ---
    path('api/fm/folder/create/', file_manager_views.api_fm_folder_create, name='api_fm_folder_create'),
    path('api/fm/folder/rename/', file_manager_views.api_fm_folder_rename, name='api_fm_folder_rename'),
    path('api/fm/folder/delete/', file_manager_views.api_fm_folder_delete, name='api_fm_folder_delete'),
    path('api/fm/folder/create-tree/', file_manager_views.api_fm_folder_create_tree, name='api_fm_folder_create_tree'),
    path('api/fm/folder/<int:folder_id>/shares/', file_manager_views.api_fm_folder_shares, name='api_fm_folder_shares'),

    # --- Шаринг ---
    path('api/fm/folder/share/', file_manager_views.api_fm_share_folder, name='api_fm_share_folder'),
    path('api/fm/folder/share/remove/', file_manager_views.api_fm_share_remove, name='api_fm_share_remove'),

    # --- Привязка файлов из inbox ---
    path('api/fm/assign/', file_manager_views.api_fm_assign, name='api_fm_assign'),

    # --- Поиск для модала привязки ---
    path('api/fm/search/', file_manager_views.api_fm_search, name='api_fm_search'),

    # --- Список сотрудников (для модалок «Поделиться») ---
    path('api/fm/employees/', file_manager_views.api_fm_employees, name='api_fm_employees'),

    # --- Совместимость со старыми маршрутами ---
    path('workspace/files/export/', file_manager_views.export_files_xlsx, name='export_files_xlsx'),
    path('workspace/files/save-columns/', file_manager_views.save_fm_columns, name='save_fm_columns'),
    path('workspace/files/save-column-widths/', file_manager_views.save_fm_column_widths, name='save_fm_column_widths'),

    # ─── equipment_views (Поверки и аттестации) — 2 новых маршрута ───
    path('workspace/equipment/maintenance-log/save-columns/', equipment_views.save_maintenance_log_columns, name='save_maintenance_log_columns'),
    path('workspace/equipment/maintenance-log/save-column-widths/', equipment_views.save_maintenance_log_column_widths, name='save_maintenance_log_column_widths'),
    # ═══════════════════════════════════════════════════════════════
    # Аналитика v4.0 — полностью переработанный дашборд
    # ═══════════════════════════════════════════════════════════════

    # Страницы
    path('workspace/analytics/',
         analytics_view, name='analytics'),
    path('workspace/analytics/employees/',
         analytics_employees_view, name='analytics_employees'),
    path('workspace/analytics/employees/<int:user_id>/',
         analytics_employee_detail_view, name='analytics_employee_detail'),

    # Справочники для фильтров
    path('workspace/analytics/api/laboratories',
         api_laboratories, name='analytics_api_laboratories'),
    path('workspace/analytics/api/test-types',
         api_test_types, name='analytics_api_test_types'),

    # Блок 1: KPI-карточки (с дельтой к прошлому периоду)
    path('workspace/analytics/api/kpi',
         api_kpi, name='analytics_api_kpi'),

    # Блок 2: Воронка этапов
    path('workspace/analytics/api/funnel',
         api_funnel, name='analytics_api_funnel'),
    path('workspace/analytics/api/stage-durations',
         api_stage_durations, name='analytics_api_stage_durations'),

    # Блок 3: Динамика
    path('workspace/analytics/api/daily-dynamics',
         api_daily_dynamics, name='analytics_api_daily_dynamics'),
    path('workspace/analytics/api/monthly-labor',
         api_monthly_labor, name='analytics_api_monthly_labor'),

    # Блок 4: Срезы
    path('workspace/analytics/api/laboratory-distribution',
         api_laboratory_distribution, name='analytics_api_lab_distribution'),
    path('workspace/analytics/api/status-distribution',
         api_status_distribution, name='analytics_api_status_distribution'),
    path('workspace/analytics/api/test-type-distribution',
         api_test_type_distribution, name='analytics_api_test_type_distribution'),
    path('workspace/analytics/api/accreditation-distribution',
         api_accreditation_distribution, name='analytics_api_accreditation_distribution'),
    path('workspace/analytics/api/report-type-distribution',
         api_report_type_distribution, name='analytics_api_report_type_distribution'),

    # Блок 5: Топы
    path('workspace/analytics/api/top-clients',
         api_top_clients, name='analytics_api_top_clients'),
    path('workspace/analytics/api/top-standards',
         api_top_standards, name='analytics_api_top_standards'),

    # Блок 6: Риски
    path('workspace/analytics/api/risk/stuck',
         api_risk_stuck_samples, name='analytics_api_risk_stuck'),
    path('workspace/analytics/api/risk/equipment-expiring',
         api_risk_equipment_expiring, name='analytics_api_risk_equipment'),
    path('workspace/analytics/api/risk/replacement-protocols',
         api_risk_replacement_protocols, name='analytics_api_risk_replacement'),

    # Блок 7: Drill-down (универсальный список образцов)
    path('workspace/analytics/api/samples/drill-down',
         api_samples_drill_down, name='analytics_api_samples_drill_down'),

    # Блок 8: Производительность сотрудников
    path('workspace/analytics/api/employees/overview',
         api_employees_overview, name='analytics_api_employees_overview'),
    path('workspace/analytics/api/employees/leaderboard',
         api_employees_leaderboard, name='analytics_api_employees_leaderboard'),
    path('workspace/analytics/api/employees/heatmap',
         api_employees_heatmap, name='analytics_api_employees_heatmap'),
    path('workspace/analytics/api/employees/<int:user_id>/detail',
         api_employee_detail, name='analytics_api_employee_detail'),
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

    # ⭐ v3.74.0: Редактирование областей аккредитации в карточке сотрудника
    # (матрица ответственности удалена — функционал перенесён сюда)
    path('workspace/employees/<int:user_id>/save-areas/', employee_views.employee_save_areas,
         name='employee_save_areas'),

    # ⭐ v3.28.0: Проверка допуска + исключения
    path('api/check-operator-accreditation/', api_check_operator_accreditation,
         name='api_check_operator_accreditation'),
    # ⭐ v3.84.0: preflight-валидация перед draft_ready/results_uploaded
    path('api/validate-draft-ready/', api_validate_draft_ready,
         name='api_validate_draft_ready'),
    # ⭐ v3.85.0 (1б+1г): preflight при смене FK на карточке образца
    path('api/validate-sample-fk-change/<int:sample_id>/', api_validate_sample_fk_change,
         name='api_validate_sample_fk_change'),

    # ⭐ v3.76.0: единая ручка user_standard_access (GRANTED/REVOKED/null)
    # из карточки стандарта.
    path('api/standards/toggle-user-access/',parameter_views.api_standard_toggle_user_access,name='api_standard_toggle_user_access'),

    # ⭐ v3.76.0: кросс-редактирование из карточки сотрудника
    path('workspace/employees/<int:user_id>/api/toggle-standard/', employee_views.api_employee_toggle_standard, name='api_employee_toggle_standard'),
    path('workspace/employees/<int:user_id>/api/update-areas/', employee_views.api_employee_update_areas, name='api_employee_update_areas'),
    # employee — рядом с api_employee_toggle_standard:
    path('workspace/employees/<int:user_id>/api/grant-standard-all/',employee_views.api_employee_grant_standard_all_areas, name='api_employee_grant_standard_all_areas'),
    path('workspace/employees/<int:user_id>/api/clear-standard-grant-all/', employee_views.api_employee_clear_standard_grant_all_areas, name='api_employee_clear_standard_grant_all_areas'),

    # equipment — рядом с api_equipment_toggle_standard:
    path('workspace/equipment/<int:equipment_id>/api/grant-standard-all/', equipment_views.api_equipment_grant_standard_all_areas, name='api_equipment_grant_standard_all_areas'),
    path('workspace/equipment/<int:equipment_id>/api/clear-standard-grant-all/', equipment_views.api_equipment_clear_standard_grant_all_areas, name='api_equipment_clear_standard_grant_all_areas'),

    # ⭐ v3.35.0: Журнал климата
    path('workspace/climate/', climate_views.climate_log_view, name='climate_log'),
    path('workspace/climate/add/', climate_views.climate_log_add, name='climate_log_add'),
    path('workspace/climate/<int:log_id>/edit/', climate_views.climate_log_edit, name='climate_log_edit'),
    path('workspace/climate/<int:log_id>/delete/', climate_views.climate_log_delete, name='climate_log_delete'),
    path('workspace/climate/quick/', climate_views.climate_quick_add, name='climate_quick_add'),
    path('workspace/climate/quick/submit/', climate_views.climate_quick_submit, name='climate_quick_submit'),
    path('workspace/climate/qr/', climate_views.climate_qr_codes, name='climate_qr_codes'),
    path('workspace/climate/export/', climate_views.export_climate_xlsx, name= 'export_climate_xlsx'),
    path('workspace/climate/room-equipment/', climate_views.climate_room_equipment, name='climate_room_equipment'),
    # ⭐ v3.35.0: Обратная связь
    path('workspace/feedback/', feedback_views.feedback_list, name='feedback_list'),
    path('workspace/feedback/create/', feedback_views.feedback_create, name='feedback_create'),
    path('workspace/feedback/<int:feedback_id>/update/', feedback_views.feedback_update, name='feedback_update'),
    path('workspace/feedback/<int:feedback_id>/delete/', feedback_views.feedback_delete, name='feedback_delete'),
    path('workspace/feedback/<int:feedback_id>/image/', feedback_views.feedback_image, name='feedback_image'),
    path('workspace/feedback/<int:feedback_id>/comment/', feedback_views.feedback_comment_add,       name='feedback_comment_add'),
    path('workspace/feedback/<int:feedback_id>/mark-read/', feedback_views.feedback_comments_mark_read, name='feedback_comments_mark_read'),

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
    # ⭐ v3.74.0: Override'ы допуска к оборудованию
    path('api/equipment/<int:equipment_id>/toggle-access/', equipment_views.api_equipment_toggle_access, name='api_equipment_toggle_access'),
    # ⭐ v3.76.0: equipment_standard_access + редактирование областей оборудования
    path('api/equipment/<int:equipment_id>/toggle-standard/', equipment_views.api_equipment_toggle_standard, name='api_equipment_toggle_standard'),
    path('api/equipment/<int:equipment_id>/update-areas/', equipment_views.api_equipment_update_areas, name='api_equipment_update_areas'),
    path('workspace/tasks/', task_views.task_list, name='task_list'),
    path('workspace/tasks/create/', task_views.task_create, name='task_create'),
    path('workspace/tasks/<int:task_id>/status/', task_views.task_update_status, name='task_update_status'),
    path('workspace/tasks/<int:task_id>/views/', task_views.task_view_details, name='task_view_details'),
    path('workspace/tasks/<int:task_id>/pin/', task_views.task_pin_toggle, name='task_pin_toggle'),
    path('workspace/tasks/<int:task_id>/activity/', task_views.task_activity, name='task_activity'),
    path('workspace/equipment/<int:equipment_id>/calibration/add/', equipment_views.equipment_add_calibration, name='equipment_add_calibration'),
    path('workspace/equipment/<int:equipment_id>/calibration/<int:calibration_id>/delete/', equipment_views.equipment_delete_calibration, name='equipment_delete_calibration'),
        # ⭐ v3.52.0: Комментарии к задачам
    path('workspace/tasks/<int:task_id>/comments/', task_views.task_comments_list, name='task_comments_list'),
    path('workspace/tasks/<int:task_id>/comments/create/', task_views.task_comment_create, name='task_comment_create'),
    path('workspace/tasks/comments/<int:comment_id>/delete/', task_views.task_comment_delete, name='task_comment_delete'),
    path('workspace/tasks/<int:task_id>/file/<int:file_id>/', task_views.task_file_view, name='task_file_view'),

    # ⭐ v3.40.0: Чат
    path('api/chat/rooms/', chat_views.api_chat_rooms, name='api_chat_rooms'),
    path('api/chat/rooms/<int:room_id>/messages/', chat_views.api_chat_messages, name='api_chat_messages'),
    path('api/chat/rooms/<int:room_id>/mark-read/', chat_views.api_chat_mark_read, name='api_chat_mark_read'),
    path('api/chat/rooms/<int:room_id>/read-status/', chat_views.api_chat_read_status, name='api_chat_read_status'),
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
    # ⭐ v3.46.0: Реакции
    path('api/chat/rooms/<int:room_id>/messages/<int:message_id>/reaction/',chat_views.api_chat_toggle_reaction, name='api_chat_toggle_reaction'),
    # Аватарки
    path('workspace/employees/<int:user_id>/avatar/upload/', employee_views.avatar_upload, name='avatar_upload'),
    path('workspace/employees/<int:user_id>/avatar/delete/', employee_views.avatar_delete, name='avatar_delete'),
    path('api/chat/forward/', chat_views.api_chat_forward_message, name='api_chat_forward'),
    path('api/chat/search/', chat_views.api_chat_search_messages, name='api_chat_search'),
    path('api/chat/rooms/<int:room_id>/pin/', chat_views.api_chat_toggle_pin, name='api_chat_toggle_pin'),
    # Иконка в браузере
    path('favicon.ico', RedirectView.as_view(url='/static/core/img/logo.png', permanent=True)),
    # пути файлов
    path('api/chat/file/<path:s3_key>', chat_views.api_chat_file, name='api_chat_file'),
    path('api/avatar/<path:s3_key>', employee_views.api_avatar, name='api_avatar'),
    path('api/fm/file/<int:file_id>/versions/', file_manager_views.api_fm_file_versions, name='api_fm_file_versions'),
    path('api/fm/file/<int:file_id>/set-current/', file_manager_views.api_fm_set_current_version, name='api_fm_set_current_version'),
    path('api/chat/rooms/<int:room_id>/messages/<int:message_id>/edit/', chat_views.api_chat_edit_message),
    path('api/chat/rooms/<int:room_id>/messages/<int:message_id>/delete/', chat_views.api_chat_delete_message),

    # API (авторизованные)
    path('api/fm/share-link/create/', shared_link_views.api_create_shared_link),
    path('api/fm/share-link/deactivate/', shared_link_views.api_deactivate_shared_link),
    path('api/fm/share-link/list/<str:target_type>/<int:target_id>/', shared_link_views.api_list_shared_links),

    # Шаринг файлов сотрудникам
    path('api/fm/file/<int:file_id>/shares/', file_manager_views.api_fm_file_shares),
    path('api/fm/file/share/', file_manager_views.api_fm_share_file),
    path('api/fm/file/unshare/', file_manager_views.api_fm_unshare_file),

    # Публичные страницы
    path('shared/<str:token>/', shared_link_views.shared_page),
    path('shared/<str:token>/download/', shared_link_views.shared_download),
    path('shared/<str:token>/download/<int:file_id>/', shared_link_views.shared_download),
    path('api/report-templates/upload/', test_report_views.api_upload_report_template, name='api_upload_report_template'),
    path('api/report-templates/', test_report_views.api_report_template_list, name='api_report_template_list'),
    path('api/report-templates/<int:source_id>/', test_report_views.api_report_template_detail, name='api_report_template_detail'),
    path('api/test-report/form/<int:sample_id>/', test_report_views.api_get_report_form, name='api_get_report_form'),
    path('api/test-report/save/', test_report_views.api_save_test_report, name='api_save_test_report'),
    path('api/test-report/calculate/', test_report_views.api_calculate_report, name='api_calculate_report'),
    path('api/test-report/<int:report_id>/export-xlsx/', test_report_views.api_export_test_report_xlsx, name='api_export_test_report_xlsx'),
    path('api/test-report/export-xlsx/<int:sample_id>/<int:standard_id>/', test_report_views.api_export_test_report_xlsx_by_sample, name='api_export_test_report_xlsx_by_sample'),

    # ── Конструктор шаблонов (новые) ────────────────────────────────────────────
    path('api/report-templates/config/save/', api_save_template_config,         name='api_save_template_config'),
    path('api/report-templates/config/delete/', api_delete_template_config,        name='api_delete_template_config'),
    path('api/report-templates/config/<int:standard_id>/', api_get_template_config,           name='api_get_template_config'),
    path('api/report-templates/config/<int:standard_id>/versions/', api_get_template_versions,         name='api_get_template_versions'), 
    path('api/report-templates/config/preview/<int:template_id>/', api_preview_template_config,       name='api_preview_template_config'),
    # ── Legacy xlsx-парсер (оставлены) ──────────────────────────────────────────
    path('api/report-templates/upload/', api_upload_report_template,        name='api_upload_report_template'),
    path('api/report-templates/',    api_report_template_list,          name='api_report_template_list'),
    path('api/report-templates/<int:source_id>/',   api_report_template_detail,        name='api_report_template_detail'),
    # ── Ввод данных и экспорт (без изменений) ───────────────────────────────────
    path('api/test-report/form/<int:sample_id>/',    api_get_report_form,               name='api_get_report_form'),
    path('api/test-report/save/',     api_save_test_report,              name='api_save_test_report'),
    path('api/test-report/calculate/',    api_calculate_report,              name='api_calculate_report'),
    path('api/test-report/<int:report_id>/export-xlsx/',    api_export_test_report_xlsx,       name='api_export_test_report_xlsx'),
    path('api/test-report/export-xlsx/<int:sample_id>/<int:standard_id>/',   api_export_test_report_xlsx_by_sample, name='api_export_test_report_xlsx_by_sample'),
    # Техработы — уведомления
    path('api/maintenance/notify/', api_maintenance_notify, name='api_maintenance_notify'),
    path('api/maintenance/cancel/', api_maintenance_cancel, name='api_maintenance_cancel'),
    path('api/maintenance/status/', api_maintenance_status, name='api_maintenance_status'),
]