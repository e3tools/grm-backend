from django import forms
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from client import get_db
from dashboard.forms.widgets import RadioSelect
from dashboard.grm import CHOICE_ANONYMOUS, CHOICE_CONTACT, CONTACT_CHOICES, MEDIUM_CHOICES
from grm.utils import (
    get_administrative_region_choices, get_administrative_region_parent, get_government_worker_choices,
    get_issue_category_choices, get_issue_status_choices, get_issue_type_choices
)

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE
MAX_LENGTH = 65000


class NewIssueStep1Form(forms.Form):
    intake_date = forms.DateTimeField(label=_('Date of Intake'), input_formats=['%d/%m/%Y'])
    issue_date = forms.DateTimeField(label=_('Date of Issue'), input_formats=['%d/%m/%Y'])
    description = forms.CharField(label=_('Summary of Issue'), max_length=2000, widget=forms.Textarea(
        attrs={'rows': '3', 'placeholder': _('Please describe the issue')}))
    issue_type = forms.ChoiceField(label=_('Type of Issue'))
    category = forms.ChoiceField(label=_('Nature of Issue'))

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial')
        doc_id = initial.get('doc_id')
        super().__init__(*args, **kwargs)

        grm_db = get_db(COUCHDB_GRM_DATABASE)
        types = get_issue_type_choices(grm_db)
        self.fields['issue_type'].widget.choices = types
        self.fields['issue_type'].choices = types
        categories = get_issue_category_choices(grm_db)
        self.fields['category'].widget.choices = categories
        self.fields['category'].choices = categories

        self.fields['intake_date'].widget.attrs['class'] = self.fields['issue_date'].widget.attrs[
            'class'] = 'form-control datetimepicker-input'
        self.fields['intake_date'].widget.attrs['data-target'] = '#intake_date'
        self.fields['issue_date'].widget.attrs['data-target'] = '#issue_date'

        document = grm_db[doc_id]
        if 'description' in document and document['description']:
            self.fields['description'].initial = document['description']
        if 'issue_type' in document and document['issue_type']:
            self.fields['issue_type'].initial = document['issue_type']['id']
        if 'category' in document and document['category']:
            self.fields['category'].initial = document['category']['id']


class NewIssueStep2Form(forms.Form):
    administrative_region = forms.ChoiceField(label=_('Issue Location'))

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial')
        doc_id = initial.get('doc_id')
        super().__init__(*args, **kwargs)

        eadl_db = get_db()
        administrative_region_choices = get_administrative_region_choices(eadl_db)
        self.fields['administrative_region'].widget.choices = administrative_region_choices
        self.fields['administrative_region'].choices = administrative_region_choices

        grm_db = get_db(COUCHDB_GRM_DATABASE)
        document = grm_db[doc_id]
        if 'administrative_region' in document and document['administrative_region']:
            administrative_id = document['administrative_region']['administrative_id']
            self.fields['administrative_region'].initial = administrative_id
            administrative_region_parent = get_administrative_region_parent(eadl_db, administrative_id)
            if administrative_region_parent:
                self.fields['administrative_region'].widget.attrs['parent_id'] = administrative_region_parent


class NewIssueStep3Form(forms.Form):
    contact_medium = forms.ChoiceField(label=_('How does the citizen wish to be contacted?'), widget=RadioSelect)
    contact_type = forms.ChoiceField(label='', required=False)
    contact = forms.CharField(label='', required=False)
    confidential_status = forms.BooleanField(label=_('Citizen wants contact information to be kept confidential'),
                                             widget=forms.CheckboxInput, required=False)
    citizen = forms.CharField(label='', required=False, help_text=_('This is an optional field'))

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial')
        doc_id = initial.get('doc_id')
        super().__init__(*args, **kwargs)

        grm_db = get_db(COUCHDB_GRM_DATABASE)

        self.fields['contact_medium'].widget.choices = MEDIUM_CHOICES
        self.fields['contact_medium'].initial = None
        self.fields['contact_medium'].choices = MEDIUM_CHOICES
        self.fields['contact_type'].widget.choices = CONTACT_CHOICES
        self.fields['contact_type'].initial = None
        self.fields['contact_type'].choices = CONTACT_CHOICES
        self.fields['contact'].widget.attrs["placeholder"] = _("Please type the contact information")
        self.fields['citizen'].widget.attrs["placeholder"] = _("Please type the name of the citizen")

        document = grm_db[doc_id]
        if 'contact_medium' in document:
            self.fields['contact_medium'].initial = document['contact_medium']
            if document['contact_medium'] == CHOICE_CONTACT:
                if 'type' in document['contact_information'] and document['contact_information']['type']:
                    self.fields['contact_type'].initial = document['contact_information']['type']
                if 'contact' in document['contact_information'] and document['contact_information']['contact']:
                    self.fields['contact'].initial = document['contact_information']['contact']
            else:
                self.fields['contact'].widget.attrs["class"] = "hidden"
                if document['contact_medium'] == CHOICE_ANONYMOUS:
                    self.fields['citizen'].widget.attrs["class"] = "hidden"

        if 'citizen' in document:
            self.fields['citizen'].initial = document['citizen']
        self.fields['confidential_status'].initial = document['confidential_status']


class NewIssueStep4Form(NewIssueStep3Form, NewIssueStep2Form, NewIssueStep1Form):

    def __init__(self, *args, **kwargs):
        NewIssueStep1Form.__init__(self, *args, **kwargs)
        NewIssueStep3Form.__init__(self, *args, **kwargs)
        self.fields['contact_medium'].label = _("Citizen Contact")


class SearchIssueForm(forms.Form):
    start_date = forms.DateTimeField(label=_('Start Date'))
    end_date = forms.DateTimeField(label=_('End Date'))
    code = forms.CharField(label=_('ID Number / Access Code'))
    assigned_to = forms.ChoiceField()
    category = forms.ChoiceField()
    type = forms.ChoiceField()
    status = forms.ChoiceField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        grm_db = get_db(COUCHDB_GRM_DATABASE)

        self.fields['start_date'].widget.attrs['class'] = self.fields['end_date'].widget.attrs[
            'class'] = 'form-control datetimepicker-input'
        self.fields['start_date'].widget.attrs['data-target'] = '#start_date'
        self.fields['end_date'].widget.attrs['data-target'] = '#end_date'
        self.fields['assigned_to'].widget.choices = get_government_worker_choices()
        self.fields['category'].widget.choices = get_issue_category_choices(grm_db)
        self.fields['type'].widget.choices = get_issue_type_choices(grm_db)
        self.fields['status'].widget.choices = get_issue_status_choices(grm_db)


class IssueDetailForm(forms.Form):
    status = forms.ChoiceField(label=_('Status'))
    assignee = forms.ChoiceField(label=_('Assigned to'))

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial')
        doc_id = initial.get('doc_id')
        super().__init__(*args, **kwargs)

        grm_db = get_db(COUCHDB_GRM_DATABASE)
        self.fields['status'].widget.choices = get_issue_status_choices(grm_db, False)
        self.fields['assignee'].widget.choices = get_government_worker_choices(False)

        document = grm_db[doc_id]
        self.fields['status'].initial = document['status']['id']
        self.fields['assignee'].initial = document['assignee']['id']


class IssueCommentForm(forms.Form):
    comment = forms.CharField(label='', max_length=MAX_LENGTH, widget=forms.Textarea(
        attrs={'rows': '3', 'placeholder': _('Add comment')}))


class IssueResearchResultForm(forms.Form):
    research_result = forms.CharField(label='', max_length=MAX_LENGTH, widget=forms.Textarea(attrs={'rows': '3'}))

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial')
        doc_id = initial.get('doc_id')
        super().__init__(*args, **kwargs)

        grm_db = get_db(COUCHDB_GRM_DATABASE)
        document = grm_db[doc_id]
        if 'research_result' in document:
            self.fields['research_result'].initial = document['research_result']
