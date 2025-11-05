from django.contrib import admin

from issues.models import AdministrativeRegion, IssueDepartment


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


admin.site.register(IssueDepartment, IssueDepartmentAdmin)
admin.site.register(AdministrativeRegion, AdministrativeRegionAdmin)
