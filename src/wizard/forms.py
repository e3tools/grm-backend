from django import forms
from django.utils.translation import gettext_lazy as _

from dashboard.models import Project


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
