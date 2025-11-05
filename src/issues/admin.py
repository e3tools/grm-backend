from django.contrib import admin

from issues.models import (
    AdministrativeRegion,
    IssueCategory,
    IssueDepartment,
    IssueDepartmentAdministrativeLevel,
)


class IssueDepartmentAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "head",
        "created_date",
        "updated_date",
    )
    raw_id_fields = ("head",)
    list_display = (
        "id",
        "name",
        "head",
        "created_date",
        "updated_date",
    )
    search_fields = (
        "name",
        "head__email",
        "head__first_name",
        "head__last_name",
    )
    readonly_fields = ("created_date", "updated_date")
    ordering = ("name",)


class AdministrativeRegionAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "administrative_level",
        "parent",
        "latitude",
        "longitude",
        "created_date",
        "updated_date",
    )
    raw_id_fields = ("parent",)
    list_display = (
        "id",
        "name",
        "administrative_level",
        "parent",
        "latitude",
        "longitude",
        "created_date",
        "updated_date",
    )
    list_filter = (
        "administrative_level",
    )
    search_fields = (
        "name",
        "administrative_level__name",
        "parent__name",
    )
    readonly_fields = ("created_date", "updated_date")
    ordering = ("name",)


class IssueCategoryAdmin(admin.ModelAdmin):
    fields = (
        "name",
        "abbreviation",
        "parent",
        "assigned_department",
        "assigned_appeal_department",
        "assigned_escalation_department",
        "confidentiality_level",
        "redirection_protocol",
        "created_date",
        "updated_date",
    )
    raw_id_fields = (
        "parent",
        "assigned_department",
        "assigned_appeal_department",
        "assigned_escalation_department",
    )
    list_display = (
        "id",
        "name",
        "abbreviation",
        "parent",
        "assigned_department",
        "confidentiality_level",
        "redirection_protocol",
        "created_date",
        "updated_date",
    )
    list_filter = (
        "confidentiality_level",
        "redirection_protocol",
        "parent",
        "created_date",
    )
    search_fields = (
        "name",
        "abbreviation",
        "parent__name",
        "assigned_department__department__name",
        "assigned_appeal_department__department__name",
        "assigned_escalation_department__department__name",
    )
    readonly_fields = ("created_date", "updated_date")
    ordering = ("name",)


class IssueDepartmentAdministrativeLevelAdmin(admin.ModelAdmin):
    fields = (
        "department",
        "administrative_level",
        "created_date",
        "updated_date",
    )
    raw_id_fields = (
        "department",
        "administrative_level",
    )
    list_display = (
        "id",
        "department",
        "administrative_level",
        "created_date",
        "updated_date",
    )
    list_filter = (
        "department",
        "administrative_level",
        "created_date",
    )
    search_fields = (
        "department__name",
        "administrative_level__name",
    )
    readonly_fields = ("created_date", "updated_date")
    ordering = ("department__name", "administrative_level__name")


admin.site.register(IssueDepartment, IssueDepartmentAdmin)
admin.site.register(AdministrativeRegion, AdministrativeRegionAdmin)
admin.site.register(IssueCategory, IssueCategoryAdmin)
admin.site.register(IssueDepartmentAdministrativeLevel, IssueDepartmentAdministrativeLevelAdmin)
