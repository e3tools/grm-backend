from zipfile import BadZipFile

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from openpyxl.utils.exceptions import InvalidFileException

from common.utils.forms import FileForm, WritableModelChoiceField
from dashboard.models import Project
from grm.constants import (
    ADMINISTRATIVE_LEVEL_DELETE_ERROR_MESSAGE,
    CATEGORY_DELETE_ERROR_MESSAGE,
    COMPONENT_DELETE_ERROR_MESSAGE,
    COMPONENT_REQUIRED_ERROR_MESSAGE,
    DEPARTMENT_DELETE_ERROR_MESSAGE,
    GROUP_DELETE_ERROR_MESSAGE,
    INVALID_EXCEL_FILE_ERROR_MESSAGE,
    ONLY_EXCEL_FILE_EXTENSIONS_ERROR_MESSAGE,
    SUBCOMPONENT_DELETE_ERROR_MESSAGE,
    SUBCOMPONENT_REQUIRED_ERROR_MESSAGE,
)
from issues.models import (
    AdministrativeLevel,
    CitizenAgeGroup,
    CitizenGroup,
    Component,
    IssueCategory,
    IssueDepartment,
    IssueDepartmentAdministrativeLevel,
    IssueStatus,
    IssueSubType,
    SubComponent,
)


class ProjectForm(forms.ModelForm):
    name = forms.CharField(
        label=_("Name"),
        widget=forms.TextInput(attrs={"placeholder": _("Enter the project name")}),
    )
    description = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": _("Please describe the project")}),
        label=_("Description"),
    )

    class Meta:
        model = Project
        fields = ["name", "description"]


class AdministrativeLevelForm(forms.ModelForm):
    class Meta:
        model = AdministrativeLevel
        fields = ["name"]
        labels = {
            "name": "",
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Enter administrative level name")}),
        }


class CustomBaseModelFormSet(forms.BaseModelFormSet):
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


AdministrativeLevelFormSet = forms.modelformset_factory(
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
        label=_("Administrative levels"),
    )

    class Meta:
        model = IssueDepartment
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Enter department name")}),
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


IssueDepartmentFormSet = forms.modelformset_factory(
    IssueDepartment,
    form=IssueDepartmentForm,
    formset=IssueDepartmentBaseFormSet,
    extra=0,
    min_num=1,
    max_num=100,
    can_delete=True,
    can_order=False,
)


class IssueCategoryForm(forms.ModelForm):
    parent = WritableModelChoiceField(
        queryset=IssueSubType.objects.all(),
        widget=forms.Select(attrs={"class": "writable", "placeholder": _("Enter a new subtype or choose one")}),
        label=_("Subtype"),
    )

    class Meta:
        model = IssueCategory
        fields = [
            "name",
            "abbreviation",
            "parent",
            "assigned_department",
            "assigned_appeal_department",
            "assigned_escalation_department",
            "confidentiality_level",
            "redirection_protocol",
        ]
        labels = {
            "assigned_department": _("Department"),
            "assigned_appeal_department": _("Appeal department"),
            "assigned_escalation_department": _("Escalation department"),
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Enter category name")}),
            "abbreviation": forms.TextInput(attrs={"placeholder": _("Enter category abbreviation")}),
            "assigned_department": forms.Select(attrs={"placeholder": _("Click to select department")}),
            "assigned_appeal_department": forms.Select(attrs={"placeholder": _("Click to select appeal department")}),
            "assigned_escalation_department": forms.Select(
                attrs={"placeholder": _("Click to select escalation department")}
            ),
            "confidentiality_level": forms.Select(attrs={"placeholder": _("Click to select confidentiality level")}),
            "redirection_protocol": forms.Select(attrs={"placeholder": _("Click to select redirection protocol")}),
        }

    def clean_parent(self):
        value = self.cleaned_data.get("parent")

        if value in (None, "", []):
            raise ValidationError(_("This field is required."))

        if isinstance(value, str):
            return IssueSubType(name=value)
        return value


class IssueCategoryBaseFormSet(CustomBaseModelFormSet):
    validation_error_message = CATEGORY_DELETE_ERROR_MESSAGE

    def save(self, commit=True):
        instances = super().save(commit=False)

        for form in self.forms:
            if not form.cleaned_data:
                continue

            if form.cleaned_data.get("DELETE", False):
                # If there is an associated category, delete it
                category = form.instance
                if category and category.pk:
                    category.delete()
                continue

            selected_sub_type = form.cleaned_data.get("parent")

            # Create new subtype
            if not selected_sub_type.id:
                sub_type, _ = IssueSubType.objects.get_or_create(name=selected_sub_type.name)
                form.instance.parent = sub_type

            # Save or update the category
            form.save(commit=commit)

            # Delete existing subtypes that are not in use
            IssueSubType.objects.exclude(Q(children__isnull=False) | Q(categories__isnull=False)).delete()

        if commit:
            for instance in instances:
                # Avoid saving deleted items
                if not instance.pk or not IssueCategory.objects.filter(pk=instance.pk).exists():
                    continue

                instance.save()

        return instances


IssueCategoryFormSet = forms.modelformset_factory(
    IssueCategory,
    form=IssueCategoryForm,
    formset=IssueCategoryBaseFormSet,
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
                "accept": ".xls,.xlsx,application/vnd.ms-excel,"
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
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


class IssueStatusForm(forms.ModelForm):
    """Form for an IssueStatus, only allows editing the name."""

    class Meta:
        model = IssueStatus
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Enter status name")}),
        }

    def has_changed(self):
        """Force it to always be considered changed to run validation."""
        return True


# Define metadata for each status flag
ISSUE_STATUS_DEFINITIONS = {
    'initial_status': {
        'name': _('Created'),
        'label': _('Represents the starting point of the issue.'),
        "help_text": _("This status indicates that the issue has just been created or initiated."),
    },
    'open_status': {
        'name': _('Open'),
        "label": _("Denotes that the issue is actively being worked on or is pending resolution."),
        "help_text": "",
    },
    'rejected_status': {
        'name': _('Rejected'),
        "label": _("Indicates that the issue has been reviewed and rejected."),
        "help_text": _("This status is used when the issue is deemed invalid or unnecessary."),
    },
    'final_status': {
        'name': _('Resolved'),
        "label": _("Marks the resolution or closure of the issue."),
        "help_text": _("This status signifies that the issue has been successfully completed or resolved."),
    },
}

STATUS_METADATA = [
    {'label': item['label'], 'help_text': item['help_text']} for item in ISSUE_STATUS_DEFINITIONS.values()
]


class IssueStatusBaseFormSet(forms.BaseModelFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for i, form in enumerate(self.forms):
            instance = form.instance
            if instance.pk:
                for flag in ('initial_status', 'open_status', 'rejected_status', 'final_status'):
                    if getattr(instance, flag):
                        form.fields['name'].label = ISSUE_STATUS_DEFINITIONS[flag]['label']
                        form.fields['name'].help_text = ISSUE_STATUS_DEFINITIONS[flag]['help_text']
                        break
            else:
                if i < len(STATUS_METADATA):
                    metadata = STATUS_METADATA[i]
                    if 'name' in form.fields:
                        form.fields['name'].label = metadata['label']
                        form.fields['name'].help_text = metadata['help_text']


ExistingIssueStatusFormSet = forms.modelformset_factory(
    IssueStatus,
    form=IssueStatusForm,
    formset=IssueStatusBaseFormSet,
    extra=0,
    can_delete=False,
)

NewIssueStatusFormSet = forms.modelformset_factory(
    IssueStatus,
    form=IssueStatusForm,
    formset=IssueStatusBaseFormSet,
    extra=len(STATUS_METADATA),
    can_delete=False,
)


class CitizenAgeGroupForm(forms.ModelForm):
    """Form for an CitizenAgeGroup, only allows editing the name."""

    class Meta:
        model = CitizenAgeGroup
        fields = ["name"]
        labels = {"name": ""}
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Enter citizen age group name")}),
        }

    def has_changed(self):
        """Force it to always be considered changed to run validation."""
        return True


DEFAULT_CITIZEN_AGE_GROUPS = (
    "Under 12 or younger",
    "12–17 years",
    "18–24 years",
    "25–34 years",
    "35–44 years",
    "45–54 years",
    "55–64 years",
    "65 and over",
)


class CitizenAgeGroupBaseFormSet(CustomBaseModelFormSet):
    validation_error_message = GROUP_DELETE_ERROR_MESSAGE


ExistingCitizenAgeGroupFormSet = forms.modelformset_factory(
    CitizenAgeGroup,
    form=CitizenAgeGroupForm,
    formset=CitizenAgeGroupBaseFormSet,
    extra=0,
    min_num=1,
    max_num=100,
    can_delete=True,
    can_order=False,
)

NewCitizenAgeGroupFormSet = forms.modelformset_factory(
    CitizenAgeGroup,
    form=CitizenAgeGroupForm,
    formset=CitizenAgeGroupBaseFormSet,
    extra=len(DEFAULT_CITIZEN_AGE_GROUPS),
    min_num=1,
    max_num=100,
    can_delete=True,
    can_order=False,
)


class CitizenGroupForm(forms.ModelForm):
    """Form for an CitizenGroup, only allows editing the name."""

    class Meta:
        model = CitizenGroup
        fields = ["name", "type"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Enter citizen group name")}),
            "type": forms.Select(
                attrs={"placeholder": _("Select the type that groups each of the options that you are creating")}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].help_text = _(
            "Use this option to classify between two different types for additional internal analysis."
        )
        self.fields["type"].required = True


class CitizenGroupBaseFormSet(CustomBaseModelFormSet):
    validation_error_message = GROUP_DELETE_ERROR_MESSAGE


ExistingCitizenGroupFormSet = forms.modelformset_factory(
    CitizenGroup,
    form=CitizenGroupForm,
    formset=CitizenGroupBaseFormSet,
    extra=0,
    max_num=100,
    can_delete=True,
    can_order=False,
)

NewCitizenGroupFormSet = forms.modelformset_factory(
    CitizenGroup,
    form=CitizenGroupForm,
    formset=CitizenGroupBaseFormSet,
    extra=1,
    max_num=100,
    can_delete=True,
    can_order=False,
)


class SubComponentForm(forms.ModelForm):
    """Form for SubComponent."""

    class Meta:
        model = SubComponent
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Enter subcomponent name')}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': _('Enter subcomponent description')}
            ),
        }


class SubComponentInlineFormSet(forms.BaseInlineFormSet):
    """Inline formset for SubComponents with validation."""

    def clean(self):
        """Ensure each Component has at least one SubComponent and validate restricted deletions."""
        super().clean()

        if any(self.errors):
            return

        # Check if the parent Component is marked for deletion
        # If so, skip the minimum SubComponent validation
        parent_form = getattr(self, 'parent_form', None)

        # Count non-deleted forms with data
        valid_forms = 0
        for form in self.forms:
            if form.cleaned_data:
                is_deleted = form.cleaned_data.get('DELETE', False)

                # Check if trying to delete a SubComponent with restricted_deletion
                if is_deleted and form.instance.pk:
                    if getattr(form.instance, 'restricted_deletion', False):
                        raise forms.ValidationError(SUBCOMPONENT_DELETE_ERROR_MESSAGE % {'name': form.instance.name})

                if parent_form and parent_form.cleaned_data.get('DELETE', False):
                    # Parent is being deleted, so we don't need to validate SubComponents
                    return

                # Count valid (non-deleted) forms
                if not is_deleted:
                    if form.cleaned_data.get('name') or form.cleaned_data.get('description'):
                        valid_forms += 1

        if valid_forms < 1:
            raise forms.ValidationError(SUBCOMPONENT_REQUIRED_ERROR_MESSAGE)


# Create inline formset for SubComponents
SubComponentFormSet = forms.inlineformset_factory(
    Component,
    SubComponent,
    form=SubComponentForm,
    formset=SubComponentInlineFormSet,
    extra=0,
    min_num=1,
    max_num=100,
    validate_min=False,
    can_delete=True,
)


class ComponentForm(forms.ModelForm):
    """Form for Component with nested SubComponents."""

    class Meta:
        model = Component
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': _('Enter component name')}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': _('Enter component description')}),
        }

    def has_changed(self):
        """Force it to always be considered changed to run validation."""
        return True


class ComponentFormSet(forms.BaseModelFormSet):
    """Custom formset for Components."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize subformsets for each component
        self.subformsets = []

        for form in self.forms:
            if form.instance.pk:
                # Existing component - load subcomponents
                subformset = SubComponentFormSet(instance=form.instance, prefix=f'subcomponent_{form.prefix}')
            else:
                # New component - empty subformset
                subformset = SubComponentFormSet(prefix=f'subcomponent_{form.prefix}')
            self.subformsets.append(subformset)

    def is_valid(self):
        """Validate main formset and all subformsets."""
        result = super().is_valid()

        # Link each subformset to its parent form for validation context
        for form, subformset in zip(self.forms, self.subformsets):
            subformset.parent_form = form
            if not subformset.is_valid():
                result = False

        return result

    def save(self, commit=True):
        """Save components and their subcomponents."""
        components = super().save(commit=commit)

        if commit:
            for component, subformset in zip(components, self.subformsets):
                if component.pk:  # Component was saved
                    subformset.instance = component
                    subformset.save()

        return components

    def clean(self):
        """Validate Components and check for restricted deletions."""
        super().clean()

        if any(self.errors):
            return

        valid_forms = 0
        for form in self.forms:
            if form.cleaned_data:
                is_deleted = form.cleaned_data.get('DELETE', False)

                # Check if trying to delete a Component with restricted_deletion
                if is_deleted and form.instance.pk:
                    if getattr(form.instance, 'restricted_deletion', False):
                        raise forms.ValidationError(COMPONENT_DELETE_ERROR_MESSAGE % {'name': form.instance.name})

                # Count valid (non-deleted) components
                if not is_deleted and form.cleaned_data.get('name'):
                    valid_forms += 1

        if valid_forms < 1:
            raise forms.ValidationError(COMPONENT_REQUIRED_ERROR_MESSAGE)


# Create the main component formset
NewComponentFormSet = forms.modelformset_factory(
    Component,
    form=ComponentForm,
    formset=ComponentFormSet,
    extra=0,
    min_num=1,
    max_num=100,
    can_delete=True,
)

ExistingComponentFormSet = forms.modelformset_factory(
    Component,
    form=ComponentForm,
    formset=ComponentFormSet,
    extra=0,
    min_num=1,
    max_num=100,
    can_delete=True,
)
