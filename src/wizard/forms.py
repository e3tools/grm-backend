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
    INVALID_EXCEL_FILE_ERROR_MESSAGE,
    ONLY_EXCEL_FILE_EXTENSIONS_ERROR_MESSAGE,
)
from issues.models import AdministrativeLevel


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


class AdministrativeLevelBaseFormSet(BaseModelFormSet):
    def clean(self):
        super().clean()

        for form in self.forms:
            if not form.cleaned_data:
                continue

            instance = form.instance
            marked_for_delete = form.cleaned_data.get("DELETE", False)

            if marked_for_delete and getattr(instance, "restricted_deletion", False):
                raise ValidationError(
                    ADMINISTRATIVE_LEVEL_DELETE_ERROR_MESSAGE,
                    code="restricted_deletion",
                    params={"name": instance.name},
                )


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
