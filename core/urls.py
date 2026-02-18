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
)
from .views.journal_views import (
    journal_samples, export_journal_xlsx,
    journal_filter_options, save_column_preferences,
)

urlpatterns = [
    path('permissions/', permissions_views.manage_permissions, name='manage_permissions'),
    path('workspace/', workspace_home, name='workspace_home'),
    path('workspace/samples/', journal_samples, name='journal_samples'),
    path('workspace/journal/samples/export/', export_journal_xlsx, name='export_journal_xlsx'),
    path('workspace/samples/filter-options/', journal_filter_options, name='journal_filter_options'),
    path('workspace/samples/save-columns/', save_column_preferences, name='save_column_preferences'),
    path('workspace/samples/create/', sample_create, name='sample_create'),
    path('workspace/samples/<int:sample_id>/', sample_detail, name='sample_detail'),
    # ⭐ v3.12.0: Разморозка блока регистрации
    path('workspace/samples/<int:sample_id>/unfreeze-registration/', unfreeze_registration_block, name='unfreeze_registration'),
    path('workspace/samples/<int:sample_id>/verify/', verification_views.verify_sample, name='verify_sample'),
    path('workspace/samples/<int:sample_id>/verify-protocol/', verification_views.verify_protocol, name='verify_protocol'),
    path('workspace/samples/<int:sample_id>/upload/', file_views.upload_sample_file, name='upload_sample_file'),
    path('workspace/files/<int:file_id>/download/', file_views.download_sample_file, name='download_sample_file'),
    path('workspace/files/<int:file_id>/view/', file_views.view_sample_file, name='view_sample_file'),
    path('workspace/files/<int:file_id>/delete/', file_views.delete_sample_file, name='delete_sample_file'),
    path('api/search-protocols/', search_protocols, name='search_protocols'),
    path('api/contracts/<int:client_id>/', api_views.get_client_contracts, name='get_client_contracts'),
    path('api/search-standards/', search_standards, name='search_standards'),
    path('logout/', logout_view, name='workspace_logout'),

    # ⭐ v3.6.0: Генератор этикеток
    path('workspace/labels/', label_views.labels_page, name='labels_page'),
    path('workspace/labels/generate/', label_views.labels_generate, name='labels_generate'),
]
