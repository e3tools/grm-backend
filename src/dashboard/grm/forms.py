from django import forms
from django.utils.translation import gettext_lazy as _

from authentication.models import GovernmentWorker
from common.utils.widgets import RadioSelect
from grm.constants import (
    ALERT_CHOICE,
    CITIZEN_TYPE_CHOICES,
    CONTACT_CHOICES,
    CONTACT_INFO_EMAIL_ERROR_MESSAGE,
    CONTACT_INFO_NO_EMAIL_ERROR_MESSAGE,
    CONTACT_MEDIUM_ERROR_MESSAGE,
    EMAIL_CHOICE,
    GENDER_CHOICES,
    MEDIUM_CHOICES,
    TEXTAREA_MAX_LENGTH,
)
from grm.utils import email_is_valid
from issues.models import (
    AdministrativeRegion,
    CitizenAgeGroup,
    CitizenGroup,
    Component,
    IssueCategory,
    IssueStatus,
    IssueSubType,
    IssueType,
    SubComponent,
    SubProjectGroup,
)


class NewIssueContactForm(forms.Form):
    contact_medium = forms.ChoiceField(
        label=_("How does the citizen wish to be contacted?"),
        widget=RadioSelect,
        choices=MEDIUM_CHOICES,
    )
    contact_type = forms.ChoiceField(label="", required=False, choices=CONTACT_CHOICES)
    contact = forms.CharField(label="", required=False)

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)

        if obj:
            self.fields["contact"].widget.attrs["placeholder"] = _("Please type the contact information")

            if obj.contact_medium:
                self.fields["contact_medium"].initial = obj.contact_medium
                if obj.contact_medium == ALERT_CHOICE:
                    if obj.contact_method:
                        self.fields["contact_type"].initial = obj.contact_method
                    if obj.contact_information:
                        self.fields["contact"].initial = obj.contact_information
                else:
                    self.fields["contact"].widget.attrs["class"] = "hidden"

    def clean(self):
        cleaned_data = super().clean()
        contact_medium = cleaned_data.get("contact_medium")
        contact_type = cleaned_data.get("contact_type")
        contact = cleaned_data.get("contact")

        if contact_medium == ALERT_CHOICE and not contact_type:
            self.add_error("contact_type", CONTACT_MEDIUM_ERROR_MESSAGE)

        elif contact_type == EMAIL_CHOICE and not email_is_valid(contact):
            self.add_error("contact", CONTACT_INFO_EMAIL_ERROR_MESSAGE)

        elif contact_type != EMAIL_CHOICE and email_is_valid(contact):
            self.add_error("contact", CONTACT_INFO_NO_EMAIL_ERROR_MESSAGE)

        return cleaned_data


class NewIssuePersonForm(forms.Form):
    citizen = forms.CharField(
        label=_("Enter name of the citizen"),
        required=False,
        help_text=_("This is an optional field"),
    )
    citizen_type = forms.ChoiceField(
        label=_(""),
        widget=RadioSelect,
        required=False,
        choices=CITIZEN_TYPE_CHOICES,
        help_text=_("This is an optional field"),
    )
    citizen_age_group = forms.ChoiceField(
        label=_("Enter age group"),
        required=False,
        help_text=_("This is an optional field"),
    )
    gender = forms.ChoiceField(
        label=_("Choose gender"),
        required=False,
        help_text=_("This is an optional field"),
        choices=GENDER_CHOICES,
    )
    citizen_group = forms.ChoiceField(
        label=_("Socio-professional group"),
        required=False,
        help_text=_("This is an optional field"),
    )

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)

        if obj:
            citizen_age_groups = CitizenAgeGroup.get_choices()
            self.fields["citizen_age_group"].widget.choices = citizen_age_groups
            self.fields["citizen_age_group"].choices = citizen_age_groups

            citizen_group_choices = CitizenGroup.get_choices()
            self.fields["citizen_group"].widget.choices = citizen_group_choices
            self.fields["citizen_group"].choices = citizen_group_choices

            citizen = obj.citizen
            if citizen:
                self.fields["citizen"].initial = citizen.name
                self.fields["citizen_type"].initial = citizen.type
                if citizen.age_group:
                    self.fields["citizen_age_group"].initial = citizen.age_group.id
                self.fields["gender"].initial = citizen.gender
                if citizen.group:
                    self.fields["citizen_group"].initial = citizen.group.id


class NewIssueDetailsForm(forms.Form):
    intake_date = forms.DateTimeField(
        label=_("Date of intake"),
        input_formats=["%d/%m/%Y"],
        help_text=_("Date when the issue was recorded on the GRM"),
    )
    issue_date = forms.DateTimeField(
        label=_("Date of issue"),
        input_formats=["%d/%m/%Y"],
        help_text=_("Date when the issue occurred"),
    )
    issue_type = forms.ChoiceField(label=_("What are you reporting"))
    issue_sub_type = forms.ModelChoiceField(queryset=IssueSubType.objects.all(), label=_("The sub type of grievance"))
    category = forms.ModelChoiceField(queryset=IssueCategory.objects.all(), label=_("The category of grievance"))
    component = forms.ChoiceField(label=_("Component"), required=False, help_text=_("This is an optional field"))
    sub_component = forms.ModelChoiceField(
        queryset=SubComponent.objects.all(),
        label=_("Sub Component"),
        required=False,
        help_text=_("This is an optional field"),
    )
    subproject_group = forms.ChoiceField(
        label=_("Subproject/ investment type"),
        required=False,
        help_text=_("This is an optional field"),
    )
    description = forms.CharField(
        label=_("Briefly describe the issue"),
        max_length=2000,
        widget=forms.Textarea(attrs={"rows": "3", "placeholder": _("Please describe the issue")}),
    )
    ongoing_issue = forms.BooleanField(
        label=_("Current event or multiple occurrences"),
        widget=forms.CheckboxInput,
        required=False,
    )

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)

        if obj:
            types = IssueType.get_choices()
            self.fields["issue_type"].widget.choices = types
            self.fields["issue_type"].choices = types

            issue_sub_types = IssueSubType.get_choices(parent=obj.issue_type) if obj.issue_type else []
            self.fields["issue_sub_type"].widget.choices = self.fields["issue_sub_type"].choices = issue_sub_types

            categories = IssueCategory.get_choices(parent=obj.issue_sub_type) if obj.issue_sub_type else []
            self.fields["category"].widget.choices = self.fields["category"].choices = categories

            components = Component.get_choices()
            self.fields["component"].widget.choices = self.fields["component"].choices = components

            sub_components = SubComponent.get_choices(parent=obj.component) if obj.component else []
            self.fields["sub_component"].widget.choices = self.fields["sub_component"].choices = sub_components

            subproject_groups = SubProjectGroup.get_choices()
            self.fields["subproject_group"].widget.choices = self.fields["subproject_group"].choices = subproject_groups

            self.fields["intake_date"].widget.attrs["class"] = self.fields["issue_date"].widget.attrs["class"] = (
                "form-control datetimepicker-input"
            )
            self.fields["intake_date"].widget.attrs["data-target"] = "#intake_date"
            self.fields["issue_date"].widget.attrs["data-target"] = "#issue_date"

            if obj.intake_date:
                self.fields["intake_date"].initial = obj.intake_date.strftime("%d/%m/%Y")
            if obj.issue_date:
                self.fields["issue_date"].initial = obj.issue_date.strftime("%d/%m/%Y")
            if obj.description:
                self.fields["description"].initial = obj.description
            if obj.issue_type:
                self.fields["issue_type"].initial = obj.issue_type.id
            if obj.issue_sub_type:
                self.fields["issue_sub_type"].initial = obj.issue_sub_type.id
            if obj.category:
                self.fields["category"].initial = obj.category.id
            if obj.component:
                self.fields["component"].initial = obj.component.id
            if obj.sub_component:
                self.fields["sub_component"].initial = obj.sub_component.id
            if obj.subproject_group:
                self.fields["subproject_group"].initial = obj.subproject_group.id
            if obj.ongoing_issue:
                self.fields["ongoing_issue"].initial = obj.ongoing_issue

        data = getattr(self, "data", None)
        if data:
            if data.get("issue_type"):
                issue_type_id = data.get("issue_type")
                issue_sub_types = IssueSubType.get_choices(parent=issue_type_id)
                self.fields["issue_sub_type"].widget.choices = self.fields["issue_sub_type"].choices = issue_sub_types
            if data.get("issue_sub_type"):
                issue_sub_type_id = data.get("issue_sub_type")
                categories = IssueCategory.get_choices(parent=issue_sub_type_id)
                self.fields["category"].widget.choices = self.fields["category"].choices = categories
            if data.get("component"):
                component_id = data.get("component")
                sub_components = SubComponent.get_choices(parent=component_id)
                self.fields["sub_component"].widget.choices = self.fields["sub_component"].choices = sub_components


class NewIssueLocationForm(forms.Form):
    administrative_region = forms.ModelChoiceField(
        queryset=AdministrativeRegion.objects.none(),
        required=True,
        label=_("Administrative Level"),
    )
    location_description = forms.CharField(
        label=_("Briefly describe the issue location"),
        max_length=2000,
        required=False,
        help_text=_("This is an optional field"),
        widget=forms.Textarea(attrs={"rows": "3", "placeholder": _("Please describe the issue location")}),
    )

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)

        if obj:
            administrative_region = obj.administrative_region
            if administrative_region:
                self.fields["administrative_region"].initial = administrative_region

            if obj.location_description:
                self.fields["location_description"].initial = obj.location_description

        data = getattr(self, "data", None)
        if data and data.get("administrative_region"):
            region_id = data.get("administrative_region")
            self.fields["administrative_region"].queryset = AdministrativeRegion.objects.filter(id=region_id)


class NewIssueConfirmForm(forms.Form):
    def __init__(self, *args, obj, **kwargs):
        super().__init__(*args, **kwargs)

        for FormClass in (NewIssueLocationForm, NewIssueDetailsForm, NewIssuePersonForm, NewIssueContactForm):
            subform = FormClass(data=self.data, obj=obj)
            for name, field in subform.fields.items():
                self.fields[name] = field


class NewIssueConfirmationForm(forms.Form):
    """Form only to show all fields and labels from NewIssueConfirmForm"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        confirm_form = NewIssueConfirmForm(*args, obj=None, **kwargs)

        for name, field in confirm_form.fields.items():
            self.fields[name] = field


class SearchIssueForm(forms.Form):
    start_date = forms.DateTimeField(label=_("Start Date"))
    end_date = forms.DateTimeField(label=_("End Date"))
    code = forms.CharField(label=_("ID Number / Access Code"))
    assigned_to = forms.ChoiceField()
    category = forms.ChoiceField()
    type = forms.ChoiceField()
    status = forms.ChoiceField()
    administrative_region = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["start_date"].widget.attrs["class"] = self.fields["end_date"].widget.attrs["class"] = (
            "form-control datetimepicker-input"
        )
        self.fields["start_date"].widget.attrs["data-target"] = "#start_date"
        self.fields["end_date"].widget.attrs["data-target"] = "#end_date"
        self.fields["assigned_to"].widget.choices = GovernmentWorker.get_choices()
        self.fields["category"].widget.choices = IssueCategory.get_choices()
        self.fields["type"].widget.choices = IssueType.get_choices()
        self.fields["status"].widget.choices = IssueStatus.get_choices()

        label = AdministrativeRegion.get_first_child_level_name()
        self.fields["administrative_region"].label = label
        self.fields["administrative_region"].widget.choices = AdministrativeRegion.get_first_level_choices()
        self.fields["administrative_region"].widget.attrs["class"] = "region"


class IssueDetailsForm(forms.Form):
    assignee = forms.ChoiceField(label=_("Assigned to"))

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)

        government_workers = GovernmentWorker.get_choices(False)
        self.fields["assignee"].widget.choices = government_workers

        # Only process assignee logic if assignee exists
        if obj.assignee:
            is_assignee_to_government_worker = False
            for worker in government_workers:
                if worker[1] == obj.assignee.id:
                    is_assignee_to_government_worker = True

            if not is_assignee_to_government_worker:
                self.fields["assignee"].widget.choices = [(obj.assignee.id, obj.assignee.name)]

            self.fields["assignee"].initial = obj.assignee.id
        else:
            # If no assignee, set initial to empty and add an empty choice
            self.fields["assignee"].widget.choices = [("", _("No assignee"))] + government_workers
            self.fields["assignee"].initial = ""


class IssueCommentForm(forms.Form):
    comment = forms.CharField(
        label="",
        max_length=TEXTAREA_MAX_LENGTH,
        widget=forms.Textarea(attrs={"rows": "3", "placeholder": _("Add comment")}),
    )


class IssueResearchResultForm(forms.Form):
    research_result = forms.CharField(
        label="", max_length=TEXTAREA_MAX_LENGTH, widget=forms.Textarea(attrs={"rows": "3"})
    )

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["research_result"].initial = obj.research_result


class IssueRejectReasonForm(forms.Form):
    reject_reason = forms.CharField(
        label="", max_length=TEXTAREA_MAX_LENGTH, widget=forms.Textarea(attrs={"rows": "3"})
    )

    def __init__(self, *args, obj=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["reject_reason"].initial = obj.reject_reason
