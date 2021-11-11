from django import forms
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.forms.fields import EmailField

from authentication.models import GovernmentWorker, User


class UserWithEmptyPasswordCreationForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "email",
        )
        field_classes = {'email': EmailField}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self._meta.model.EMAIL_FIELD in self.fields:
            self.fields[self._meta.model.EMAIL_FIELD].widget.attrs['autofocus'] = True


class UserAdmin(BaseUserAdmin):
    add_form = UserWithEmptyPasswordCreationForm
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'photo'),
        }),
    )
    fieldsets = (
        (None, {
            'fields': ('username', 'password', 'first_name', 'last_name', 'photo', 'email', 'is_active', 'is_staff',
                       'is_superuser', 'groups', 'user_permissions')
        }),
    )
    list_display = ('id', 'email', 'username', 'first_name', 'last_name', 'is_staff')


class GovernmentWorkerAdmin(admin.ModelAdmin):
    fields = (
        'user',
        'department',
    )
    raw_id_fields = (
        'user',
    )
    list_display = (
        'id',
        'user',
        'department',
    )
    search_fields = (
        'id',
        'user__email',
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


class LogEntryAdmin(admin.ModelAdmin):
    list_filter = [
        'content_type',
        'action_flag'
    ]

    search_fields = [
        'user__username',
        'object_repr',
        'change_message'
    ]

    list_display = [
        'action_time',
        'user',
        'content_type',
        'action_flag',
        'change_message',
    ]

    def queryset(self, request):
        return super().queryset(request).prefetch_related('content_type')


admin.site.register(User, UserAdmin)
admin.site.register(GovernmentWorker, GovernmentWorkerAdmin)
admin.site.register(LogEntry, LogEntryAdmin)
