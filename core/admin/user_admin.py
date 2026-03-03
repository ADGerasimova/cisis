from django.contrib import admin
from django.contrib import messages
from django import forms
from django.core.exceptions import ValidationError

from core.models import User, UserAdditionalLaboratory


# ═══════════════════════════════════════════════════════════════
# ⭐ v3.8.0: Инлайн для дополнительных лабораторий
# ═══════════════════════════════════════════════════════════════

class UserAdditionalLaboratoryInline(admin.TabularInline):
    model = UserAdditionalLaboratory
    extra = 1
    verbose_name = 'Дополнительная лаборатория'
    verbose_name_plural = 'Дополнительные лаборатории'


# ═══════════════════════════════════════════════════════════════
# ⭐ v3.8.0: Форма с валидацией наставника
# ═══════════════════════════════════════════════════════════════

class UserAdminForm(forms.ModelForm):
    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if 'mentor' in self.fields:
            # Показываем только активных не-стажёров
            qs = User.objects.filter(
                is_active=True,
                is_trainee=False,
            ).order_by('last_name', 'first_name')

            # Исключаем самого себя
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            # Фильтруем по подразделению
            if self.instance and self.instance.laboratory_id:
                qs = qs.filter(laboratory=self.instance.laboratory)

            self.fields['mentor'].queryset = qs

    def clean(self):
        cleaned_data = super().clean()
        is_trainee = cleaned_data.get('is_trainee', False)
        mentor = cleaned_data.get('mentor')
        laboratory = cleaned_data.get('laboratory')

        if is_trainee and not mentor:
            raise ValidationError(
                'Для стажёра обязательно указать наставника.'
            )

        if mentor:
            if mentor.is_trainee:
                raise ValidationError(
                    'Наставник не может быть стажёром.'
                )
            if self.instance and mentor.pk == self.instance.pk:
                raise ValidationError(
                    'Пользователь не может быть наставником самому себе.'
                )
            if laboratory and mentor.laboratory_id != laboratory.id:
                raise ValidationError(
                    f'Наставник должен быть из того же подразделения. '
                    f'Наставник: {mentor.laboratory}, сотрудник: {laboratory}.'
                )

        return cleaned_data


# ═══════════════════════════════════════════════════════════════
# АДМИНКА ПОЛЬЗОВАТЕЛЕЙ
# ═══════════════════════════════════════════════════════════════

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    form = UserAdminForm  # ⭐ v3.8.0
    inlines = [UserAdditionalLaboratoryInline]  # ⭐ v3.8.0

    list_display = [
        'username', 'full_name_display', 'role', 'laboratory',
        'is_trainee_display', 'mentor', 'is_active',
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
            'fields': ('username', 'last_name', 'first_name', 'sur_name', 'email')
        }),
        ('Роль и подразделение', {
            'fields': ('role', 'laboratory', 'is_staff', 'is_superuser')
        }),
        # ⭐ v3.8.0: Новый блок
        ('Стажёр и наставничество', {
            'fields': ('is_trainee', 'mentor'),
            'description': (
                'Отметьте «Стажёр», если сотрудник проходит стажировку. '
                'Наставник обязателен для стажёра и должен быть из того же подразделения.'
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

    def full_name_display(self, obj):
        return obj.full_name

    full_name_display.short_description = 'ФИО'
    full_name_display.admin_order_field = 'last_name'