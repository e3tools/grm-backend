from zipfile import BadZipFile

from django import forms
from django.core.exceptions import ValidationError
from django.forms import BaseModelFormSet, modelformset_factory
from django.utils.translation import gettext_lazy as _
from openpyxl.utils.exceptions import InvalidFileException

from dashboard.forms.forms import FileForm
from dashboard.models import Project
from grm.constants import (
    ADMINISTRATIVE_LEVEL_DELETE_ERROR_MESSAGE,
    DEPARTMENT_DELETE_ERROR_MESSAGE,
    INVALID_EXCEL_FILE_ERROR_MESSAGE,
    ONLY_EXCEL_FILE_EXTENSIONS_ERROR_MESSAGE,
)
from issues.models import (
    AdministrativeLevel,
    IssueDepartment,
    IssueDepartmentAdministrativeLevel,
)


class ProjectForm(forms.ModelForm):
    name = forms.CharField(
        label=_("Project Name"),
        widget=forms.TextInput(attrs={"placeholder": _("Enter the project name")}),
    )
    description = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": "3", "placeholder": _("Please describe the project")}),
        label=_("Project Description"),
    )

    class Meta:
        model = Project
        fields = ["name", "description"]


class AdministrativeLevelForm(forms.ModelForm):
    name = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": _("Enter administrative level name")})
    )

    class Meta:
        model = AdministrativeLevel
        fields = ["name"]


class CustomBaseModelFormSet(BaseModelFormSet):
    validation_error_message = ADMINISTRATIVE_LEVEL_DELETE_ERROR_MESSAGE

    def clean(self):
        super().clean()

        for form in self.forms:
            if not form.cleaned_data:
                continue

            instance = form.instance
            marked_for_delete = form.cleaned_data.get("DELETE", False)

            if marked_for_delete and getattr(instance, "restricted_deletion", False):
                raise ValidationError(
                    self.validation_error_message,
                    code="restricted_deletion",
                    params={"name": instance.name},
                )


class AdministrativeLevelBaseFormSet(CustomBaseModelFormSet):
    pass


AdministrativeLevelFormSet = modelformset_factory(
    AdministrativeLevel,
    form=AdministrativeLevelForm,
    formset=AdministrativeLevelBaseFormSet,
    extra=0,
    min_num=1,
    max_num=100,
    can_delete=True,
    can_order=False,
)


class IssueDepartmentForm(forms.ModelForm):
    administrative_levels = forms.ModelMultipleChoiceField(
        queryset=AdministrativeLevel.objects.all(),
        widget=forms.SelectMultiple(attrs={"placeholder": _("Click to select administrative levels")}),
        label=_("Administrative Levels"),
    )

    class Meta:
        model = IssueDepartment
        fields = ["name"]
        labels = {
            "name": _("Department Name"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            # preload already related levels
            existing_levels = AdministrativeLevel.objects.filter(
                issuedepartmentadministrativelevel__department=self.instance
            )
            self.fields["administrative_levels"].initial = existing_levels


class IssueDepartmentBaseFormSet(CustomBaseModelFormSet):
    validation_error_message = DEPARTMENT_DELETE_ERROR_MESSAGE

    def save(self, commit=True):
        instances = super().save(commit=False)

        for form in self.forms:
            if not form.cleaned_data:
                continue

            if form.cleaned_data.get("DELETE", False):
                # If there is an associated department, delete it
                department = form.instance
                if department and department.pk:
                    department.delete()
                continue

            # Save or update the department
            department = form.save(commit=commit)

            selected_levels = form.cleaned_data.get("administrative_levels", [])

            # Delete existing relationships that are not selected
            IssueDepartmentAdministrativeLevel.objects.filter(department=department).exclude(
                administrative_level__in=selected_levels
            ).delete()

            # Create new relationships
            for level in selected_levels:
                IssueDepartmentAdministrativeLevel.objects.get_or_create(
                    department=department,
                    administrative_level=level,
                )

        if commit:
            for instance in instances:
                # Avoid saving deleted items
                if not instance.pk or not IssueDepartment.objects.filter(pk=instance.pk).exists():
                    continue

                instance.save()

        return instances


IssueDepartmentFormSet = modelformset_factory(
    IssueDepartment,
    form=IssueDepartmentForm,
    formset=IssueDepartmentBaseFormSet,
    extra=0,
    min_num=1,
    max_num=100,
    can_delete=True,
    can_order=False,
)


class UploadAdministrativeRegionForm(FileForm):
    file = forms.FileField(
        label=_("Upload Excel File"),
        widget=forms.ClearableFileInput(
            attrs={
                "accept": ".xls,.xlsx,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            }
        ),
    )

    def clean_file(self):
        value = super().clean_file()
        if not value:
            return value

        # Check extension
        if not value.name.lower().endswith((".xls", ".xlsx")):
            raise forms.ValidationError(ONLY_EXCEL_FILE_EXTENSIONS_ERROR_MESSAGE)

        # Check that it is really an Excel
        from openpyxl import load_workbook

        try:
            load_workbook(value)
        except (InvalidFileException, BadZipFile):
            raise forms.ValidationError(INVALID_EXCEL_FILE_ERROR_MESSAGE)

        return value
