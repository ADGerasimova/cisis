from django.contrib import admin
from django.contrib import messages
from django import forms
from django.core.exceptions import ValidationError

from core.models import User, UserAdditionalLaboratory, UserMentor


# ═══════════════════════════════════════════════════════════════
# ⭐ v3.8.0: Инлайн для дополнительных лабораторий
# ═══════════════════════════════════════════════════════════════

class UserAdditionalLaboratoryInline(admin.TabularInline):
    model = UserAdditionalLaboratory
    extra = 1
    verbose_name = 'Дополнительная лаборатория'
    verbose_name_plural = 'Дополнительные лаборатории'


# ═══════════════════════════════════════════════════════════════
# ⭐ v3.86.0: Инлайн для наставников
# ═══════════════════════════════════════════════════════════════
# M2M с явной through-моделью нельзя положить в fieldsets/filter_horizontal
# (admin.E013). Поэтому используем TabularInline по паттерну
# UserAdditionalLaboratoryInline. fk_name='user' обязателен — у UserMentor
# два FK на User (user и mentor), Django сам не угадает, какой основной.
# ═══════════════════════════════════════════════════════════════

class UserMentorInline(admin.TabularInline):
    model = UserMentor
    fk_name = 'user'
    extra = 1
    verbose_name = 'Наставник'
    verbose_name_plural = 'Наставники'
    raw_id_fields = ('mentor',)  # компактный виджет вместо тяжёлого dropdown


# ═══════════════════════════════════════════════════════════════
# ⭐ v3.8.0 / v3.86.0: Форма User
# ═══════════════════════════════════════════════════════════════
# Валидация наставников перенесена в слой views (employee_add / employee_edit)
# и в inline-строки. Django ModelForm с fields='__all__' не включает M2M
# с явной through-моделью — поле 'mentors' в self.fields не попадёт.
# ═══════════════════════════════════════════════════════════════

class UserAdminForm(forms.ModelForm):
    class Meta:
        model = User
        fields = '__all__'


# ═══════════════════════════════════════════════════════════════
# АДМИНКА ПОЛЬЗОВАТЕЛЕЙ
# ═══════════════════════════════════════════════════════════════

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserAdminForm  # ⭐ v3.8.0
    inlines = [UserAdditionalLaboratoryInline, UserMentorInline]  # ⭐ v3.86.0

    list_display = [
        'username', 'full_name_display', 'role', 'laboratory',
        'is_trainee_display', 'mentors_display', 'is_active',  # ⭐ v3.86.0
    ]
    list_filter = ['is_active', 'role', 'laboratory', 'is_trainee']  # ⭐ v3.8.0
    search_fields = ['username', 'first_name', 'last_name', 'sur_name', 'email']

    # ═══════════════════════════════════════════════════════════════
    # БЛОКИРОВКА УДАЛЕНИЯ
    # ═══════════════════════════════════════════════════════════════

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    # ═══════════════════════════════════════════════════════════════
    # ДЕЙСТВИЯ
    # ═══════════════════════════════════════════════════════════════

    @admin.action(description='❌ Деактивировать выбранных пользователей')
    def deactivate_users(self, request, queryset):
        count = queryset.filter(is_active=True).count()
        queryset.update(is_active=False)
        self.message_user(request, f'Деактивировано пользователей: {count}', messages.SUCCESS)

    @admin.action(description='✅ Активировать выбранных пользователей')
    def activate_users(self, request, queryset):
        count = queryset.filter(is_active=False).count()
        queryset.update(is_active=True)
        self.message_user(request, f'Активировано пользователей: {count}', messages.SUCCESS)

    actions = [deactivate_users, activate_users]

    # ═══════════════════════════════════════════════════════════════
    # ГРУППИРОВКА ПОЛЕЙ
    # ═══════════════════════════════════════════════════════════════

    fieldsets = (
        ('Основная информация', {
            'fields': ('username', 'last_name', 'first_name', 'sur_name', 'email', 'phone')
        }),
        ('Роль и подразделение', {
            'fields': ('role', 'laboratory', 'position', 'is_staff', 'is_superuser')
        }),
        # ⭐ v3.86.0: Только флаг стажёра; наставники управляются инлайном ниже
        ('Стажёр', {
            'fields': ('is_trainee',),
            'description': (
                'Отметьте «Стажёр», если сотрудник проходит стажировку. '
                'Наставники назначаются в отдельной секции «Наставники» ниже на этой странице.'
            ),
        }),
        ('Статус', {
            'fields': ('is_active',),
            'description': 'Деактивированные пользователи не могут войти в систему'
        }),
        ('Пароль', {
            'fields': ('password_hash',),
            'classes': ('collapse',),
        }),
    )

    readonly_fields = ['last_login', 'created_at', 'updated_at']

    # ⭐ v3.8.0: Отображение статуса стажёра в списке
    def is_trainee_display(self, obj):
        if obj.is_trainee:
            return '👨‍🎓 Стажёр'
        return '—'
    is_trainee_display.short_description = 'Стажёр'
    is_trainee_display.admin_order_field = 'is_trainee'

    # ⭐ v3.86.0: Отображение наставников (M2M) в списке
    def mentors_display(self, obj):
        names = [m.short_name for m in obj.mentors.all()]
        return ', '.join(names) if names else '—'
    mentors_display.short_description = 'Наставники'

    def full_name_display(self, obj):
        return obj.full_name

    full_name_display.short_description = 'ФИО'
    full_name_display.admin_order_field = 'last_name'

    # ═══════════════════════════════════════════════════════════════
    # ⭐ v3.86.0: ОПТИМИЗАЦИЯ ЗАПРОСОВ ДЛЯ LIST_DISPLAY
    # ═══════════════════════════════════════════════════════════════

    def get_queryset(self, request):
        """prefetch_related для mentors, чтобы избежать N+1 в списке."""
        return super().get_queryset(request).prefetch_related('mentors')