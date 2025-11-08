from zipfile import BadZipFile

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from openpyxl.utils.exceptions import InvalidFileException

from common.utils.forms import FileForm, WritableModelMultipleChoiceField
from dashboard.models import Project
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
    IssueType,
    SubComponent,
)
from wizard.constants import (
    INVALID_EXCEL_FILE_ERROR_MESSAGE,
    ITEM_DELETE_ERROR_MESSAGE,
    ONLY_EXCEL_FILE_EXTENSIONS_ERROR_MESSAGE,
    SUBCOMPONENT_REQUIRED_ERROR_MESSAGE,
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
    validation_error_message = ITEM_DELETE_ERROR_MESSAGE

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


AdministrativeLevelFormSet = forms.modelformset_factory(
    AdministrativeLevel,
    form=AdministrativeLevelForm,
    formset=CustomBaseModelFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=100,
    validate_max=True,
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
    validate_min=True,
    max_num=100,
    validate_max=True,
    can_delete=True,
    can_order=False,
)

DEFAULT_ISSUE_TYPES = ("Grievance", "Feedback", "Question")


class IssueTypeForm(forms.ModelForm):
    subtypes = WritableModelMultipleChoiceField(
        queryset=IssueSubType.objects.none(),
        widget=forms.SelectMultiple(
            attrs={"class": "writable", "placeholder": _("Enter a new subtypes or choose one")}
        ),
        label=_("Subtypes"),
    )

    class Meta:
        model = IssueType
        fields = ["name", "subtypes"]
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Enter type name")}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance.pk:
            # preload already related levels
            existing_subtypes = IssueSubType.objects.filter(parent=self.instance).select_related('parent')
            self.fields["subtypes"].queryset = self.fields["subtypes"].initial = existing_subtypes

    def clean_subtypes(self):
        values = self.cleaned_data.get("subtypes", [])

        if not values:
            raise ValidationError(_("This field is required."))

        cleaned = []
        for value in values:

            if isinstance(value, str):
                subtype = IssueSubType(name=value)
                cleaned.append(subtype)
            else:
                cleaned.append(value)

        return cleaned

    def has_changed(self):
        """Force it to always be considered changed to run validation."""
        return True


class IssueTypeBaseFormSet(CustomBaseModelFormSet):

    def save(self, commit=True):
        instances = super().save(commit=False)
        all_selected_subtypes_ids = []

        for form in self.forms:
            if not form.cleaned_data:
                continue

            issue_type = form.instance
            if form.cleaned_data.get("DELETE", False):
                # If there is an associated issue type, delete it
                if issue_type and issue_type.pk:
                    issue_type.delete()
                continue

            # Save or update the issue type
            form.save(commit=commit)

            selected_subtypes = form.cleaned_data.get("subtypes")

            selected_subtypes_ids = []
            for selected_subtype in selected_subtypes:
                if not selected_subtype.id:
                    # Create new subtypes
                    new_subtype, _ = IssueSubType.objects.get_or_create(name=selected_subtype.name, parent=issue_type)
                    selected_subtypes_ids.append(new_subtype.id)
                else:
                    selected_subtypes_ids.append(selected_subtype.id)

            all_selected_subtypes_ids.extend(selected_subtypes_ids)

            # Remove subtypes that are no longer selected
            IssueSubType.objects.filter(parent=issue_type).exclude(
                Q(id__in=selected_subtypes_ids) | Q(categories__isnull=False)
            ).delete()

        if commit:
            for instance in instances:
                # Avoid saving deleted items
                if not instance.pk or not IssueType.objects.filter(pk=instance.pk).exists():
                    continue

                instance.save()

        return instances


class NewIssueTypeBaseFormSet(IssueTypeBaseFormSet):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for i, form in enumerate(self.forms):
            if i < len(DEFAULT_ISSUE_TYPES) and not form.instance.pk:
                form.initial['name'] = DEFAULT_ISSUE_TYPES[i]


ExistingIssueTypeFormSet = forms.modelformset_factory(
    IssueType,
    form=IssueTypeForm,
    formset=IssueTypeBaseFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=100,
    validate_max=True,
    can_delete=True,
    can_order=False,
)

NewIssueTypeFormSet = forms.modelformset_factory(
    IssueType,
    form=IssueTypeForm,
    formset=NewIssueTypeBaseFormSet,
    extra=len(DEFAULT_ISSUE_TYPES) - 1,
    min_num=1,
    validate_min=True,
    max_num=100,
    validate_max=True,
    can_delete=True,
    can_order=False,
)


class IssueCategoryForm(forms.ModelForm):
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
            "parent": _("Subtype"),
            "assigned_department": _("Department"),
            "assigned_appeal_department": _("Appeal department"),
            "assigned_escalation_department": _("Escalation department"),
        }
        widgets = {
            "name": forms.TextInput(attrs={"placeholder": _("Enter category name")}),
            "abbreviation": forms.TextInput(attrs={"placeholder": _("Enter category abbreviation")}),
            "parent": forms.Select(attrs={"placeholder": _("Click to select subtype")}),
            "assigned_department": forms.Select(attrs={"placeholder": _("Click to select department")}),
            "assigned_appeal_department": forms.Select(attrs={"placeholder": _("Click to select appeal department")}),
            "assigned_escalation_department": forms.Select(
                attrs={"placeholder": _("Click to select escalation department")}
            ),
            "confidentiality_level": forms.Select(attrs={"placeholder": _("Click to select confidentiality level")}),
            "redirection_protocol": forms.Select(attrs={"placeholder": _("Click to select redirection protocol")}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Force parent to be required even if model allows blank/null
        self.fields["parent"].required = True

        # Customize how the subtype options are displayed
        self.fields["parent"].label_from_instance = lambda obj: f"{obj.name} ({obj.parent.name})"


IssueCategoryFormSet = forms.modelformset_factory(
    IssueCategory,
    form=IssueCategoryForm,
    formset=CustomBaseModelFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=100,
    validate_max=True,
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

    def clean(self):
        cleaned_data = super().clean()
        file_field = self.file_field_name
        value = cleaned_data.get(file_field)
        if value:
            # Check extension
            if not value.name.lower().endswith((".xls", ".xlsx")):
                raise forms.ValidationError(ONLY_EXCEL_FILE_EXTENSIONS_ERROR_MESSAGE)

            # Check that it is really an Excel
            from openpyxl import load_workbook

            try:
                load_workbook(value)
            except (InvalidFileException, BadZipFile):
                raise forms.ValidationError(INVALID_EXCEL_FILE_ERROR_MESSAGE)

        return cleaned_data


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
        'label': _('Represents the starting point of the issue'),
        "help_text": _("This status indicates that the issue has just been created or initiated."),
    },
    'open_status': {
        'name': _('Open'),
        "label": _("Denotes that the issue is actively being worked on or is pending resolution"),
        "help_text": "",
    },
    'rejected_status': {
        'name': _('Rejected'),
        "label": _("Indicates that the issue has been reviewed and rejected"),
        "help_text": _("This status is used when the issue is deemed invalid or unnecessary."),
    },
    'final_status': {
        'name': _('Resolved'),
        "label": _("Marks the resolution or closure of the issue"),
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

ExistingCitizenAgeGroupFormSet = forms.modelformset_factory(
    CitizenAgeGroup,
    form=CitizenAgeGroupForm,
    formset=CustomBaseModelFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=100,
    validate_max=True,
    can_delete=True,
    can_order=False,
)

NewCitizenAgeGroupFormSet = forms.modelformset_factory(
    CitizenAgeGroup,
    form=CitizenAgeGroupForm,
    formset=CustomBaseModelFormSet,
    extra=len(DEFAULT_CITIZEN_AGE_GROUPS) - 1,
    min_num=1,
    validate_min=True,
    max_num=100,
    validate_max=True,
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


ExistingCitizenGroupFormSet = forms.modelformset_factory(
    CitizenGroup,
    form=CitizenGroupForm,
    formset=CustomBaseModelFormSet,
    extra=0,
    max_num=100,
    validate_max=True,
    can_delete=True,
    can_order=False,
)

NewCitizenGroupFormSet = forms.modelformset_factory(
    CitizenGroup,
    form=CitizenGroupForm,
    formset=CustomBaseModelFormSet,
    extra=1,
    max_num=100,
    validate_max=True,
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
                        raise forms.ValidationError(ITEM_DELETE_ERROR_MESSAGE % {'name': form.instance.name})

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
    max_num=100,
    validate_max=True,
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

        for form in self.forms:
            if form.cleaned_data:
                is_deleted = form.cleaned_data.get('DELETE', False)

                # Check if trying to delete a Component with restricted_deletion
                if is_deleted and form.instance.pk:
                    if getattr(form.instance, 'restricted_deletion', False):
                        raise forms.ValidationError(ITEM_DELETE_ERROR_MESSAGE % {'name': form.instance.name})


# Create the main component formset
NewComponentFormSet = forms.modelformset_factory(
    Component,
    form=ComponentForm,
    formset=ComponentFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=100,
    validate_max=True,
    can_delete=True,
)

ExistingComponentFormSet = forms.modelformset_factory(
    Component,
    form=ComponentForm,
    formset=ComponentFormSet,
    extra=0,
    min_num=1,
    validate_min=True,
    max_num=100,
    validate_max=True,
    can_delete=True,
)
