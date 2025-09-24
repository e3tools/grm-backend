from django import forms
from django.forms import modelformset_factory
from django.utils.translation import gettext_lazy as _

from dashboard.models import Project
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


AdministrativeLevelFormSet = modelformset_factory(
    AdministrativeLevel,
    form=AdministrativeLevelForm,
    extra=0,
    min_num=1,
    max_num=100,
    can_delete=True,
    can_order=False,
)
