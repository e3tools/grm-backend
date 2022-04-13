from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from authentication.models import GovernmentWorker, get_assignee
from client import get_db, upload_file
from dashboard.forms.forms import FileForm
from dashboard.grm import CHOICE_CONTACT
from dashboard.grm.forms import (
    IssueCommentForm, IssueDetailsForm, IssueRejectReasonForm, IssueResearchResultForm, MAX_LENGTH, NewIssueConfirmForm,
    NewIssueContactForm, NewIssueDetailsForm, NewIssueLocationForm, NewIssuePersonForm, SearchIssueForm
)
from dashboard.mixins import AJAXRequestMixin, JSONResponseMixin, ModalFormMixin, PageMixin
from grm.utils import (
    get_administrative_level_descendants, get_auto_increment_id, get_child_administrative_levels,
    get_parent_administrative_level
)

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE
COUCHDB_GRM_ATTACHMENT_DATABASE = settings.COUCHDB_GRM_ATTACHMENT_DATABASE


class DashboardTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'grm/dashboard.html'
    title = _('GRM')
    active_level1 = 'grm'
    breadcrumb = [
        {
            'url': '',
            'title': title
        },
    ]


class StartNewIssueView(LoginRequiredMixin, generic.View):

    def post(self, request, *args, **kwargs):
        grm_db = get_db(COUCHDB_GRM_DATABASE)
        auto_increment_id = get_auto_increment_id(grm_db)
        user = request.user
        issue = {
            "auto_increment_id": auto_increment_id,
            "reporter": {
                "id": user.id,
                "name": user.name
            },
            "created_date": datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            "confirmed": False,
            "escalate_flag": False,
            "created_by": False,
            "type": "issue"
        }
        grm_db.create_document(issue)
        return HttpResponseRedirect(
            reverse('dashboard:grm:new_issue_step_1', kwargs={'issue': issue['auto_increment_id']}))


class IssueMixin:
    doc = None
    grm_db = None
    eadl_db = None
    max_attachments = 20
    permissions = ('read', 'write')
    has_permission = True

    def get_query_result(self, **kwargs):
        return self.grm_db.get_query_result({
            "auto_increment_id": kwargs['issue'],
            "type": 'issue'
        })

    def check_permissions(self):
        user = self.request.user

        if self.doc["confirmed"]:
            if 'read_only_by_reporter' in self.permissions and self.doc['reporter']['id'] != user.id:
                self.has_permission = False
            else:
                if hasattr(user, 'governmentworker') and self.doc['assignee']['id'] != user.id:
                    if 'read' not in self.permissions and \
                            'read_only_by_reporter' not in self.permissions:
                        self.has_permission = False
                    else:
                        if 'read_only_by_reporter' in self.permissions:
                            if self.doc['reporter']['id'] != user.id:
                                self.has_permission = False
                        else:
                            if not user.governmentworker.has_read_permission_for_issue(self.eadl_db, self.doc):
                                self.has_permission = False
                            if 'write' not in self.permissions:
                                self.has_permission = False

    def dispatch(self, request, *args, **kwargs):
        self.grm_db = get_db(COUCHDB_GRM_DATABASE)
        self.eadl_db = get_db()
        docs = self.get_query_result(**kwargs)
        try:
            self.doc = self.grm_db[docs[0][0]['_id']]
        except Exception:
            raise Http404

        self.check_permissions()
        if not self.has_permission:
            raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['doc'] = self.doc
        context['max_attachments'] = self.max_attachments
        context['choice_contact'] = CHOICE_CONTACT
        permission_to_edit = True
        user = self.request.user
        if hasattr(user, 'governmentworker') and self.doc['assignee']['id'] != user.id:
            permission_to_edit = False
        context['permission_to_edit'] = permission_to_edit
        return context


class UploadIssueAttachmentFormView(IssueMixin, AJAXRequestMixin, ModalFormMixin, LoginRequiredMixin, JSONResponseMixin,
                                    generic.FormView):
    form_class = FileForm
    title = _('Add attachment')
    submit_button = _('Upload')
    permissions = ('read',)

    def form_valid(self, form):
        data = form.cleaned_data
        attachments = self.doc['attachments'] if 'attachments' in self.doc else list()
        if len(attachments) < self.max_attachments:
            response = upload_file(data['file'], COUCHDB_GRM_ATTACHMENT_DATABASE)
            if response['ok']:
                attachment = {
                    "name": data["file"].name,
                    "url": f'/grm_attachments/{response["id"]}/{data["file"].name}',
                    "local_url": "",
                    "id": datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                    "uploaded": True,
                    "bd_id": response['id'],
                }
                attachments.append(attachment)
                self.doc['attachments'] = attachments
                self.doc.save()
                msg = _("The attachment was successfully uploaded.")
                messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')
            else:
                msg = _("An error has occurred that did not allow the attachment to be uploaded to the database. "
                        "Please report to IT staff.")
                messages.add_message(self.request, messages.ERROR, msg, extra_tags='danger')
        else:
            msg = _("The file could not be uploaded because it has already reached the limit of %(max)d attachments."
                    ) % {'max': self.max_attachments}
            messages.add_message(self.request, messages.ERROR, msg, extra_tags='danger')
        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class IssueAttachmentDeleteView(IssueMixin, AJAXRequestMixin, ModalFormMixin, LoginRequiredMixin, JSONResponseMixin,
                                generic.DeleteView):
    permissions = ('read',)

    def delete(self, request, *args, **kwargs):
        if 'attachments' in self.doc:
            attachments = self.doc['attachments']
            grm_attachment_db = get_db(COUCHDB_GRM_ATTACHMENT_DATABASE)
            for attachment in attachments:
                if attachment['id'] == kwargs['attachment']:
                    try:
                        grm_attachment_db[attachment['bd_id']].delete()
                    except Exception:
                        pass
                    attachments.remove(attachment)
                    break
            self.doc.save()
            msg = _("The attachment was successfully deleted.")
            messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')
            context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
            return self.render_to_json_response(context, safe=False)
        else:
            raise Http404


class IssueAttachmentListView(IssueMixin, AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'grm/issue_attachments.html'
    context_object_name = 'attachments'

    def get_queryset(self):
        return self.doc['attachments'] if 'attachments' in self.doc else list()

    def dispatch(self, request, *args, **kwargs):
        column = self.request.GET.get('column', '')
        if column:
            self.template_name = 'grm/issue_attachments_column1.html'
        return super().dispatch(request, *args, **kwargs)


class IssueFormMixin(IssueMixin, generic.FormView):

    def get_form_kwargs(self):
        self.initial = {'doc_id': self.doc['_id']}
        return super().get_form_kwargs()


class NewIssueMixin(LoginRequiredMixin, IssueFormMixin):
    fields_to_check = None

    def dispatch(self, request, *args, **kwargs):
        dispatch = super().dispatch(request, *args, **kwargs)
        if self.fields_to_check and not self.has_required_fields():
            raise Http404
        return dispatch

    def get_query_result(self, **kwargs):
        return self.grm_db.get_query_result({
            "auto_increment_id": kwargs['issue'],
            "reporter.id": self.request.user.id,
            "confirmed": False,
            "type": 'issue'
        })

    def get_form_kwargs(self):
        self.initial = {'doc_id': self.doc['_id']}
        return super().get_form_kwargs()

    def has_required_fields(self):
        for field in self.fields_to_check:
            if field not in self.doc:
                return False
        return True

    def set_details_fields(self, data):
        self.doc['intake_date'] = data['intake_date'].strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        self.doc['issue_date'] = data['issue_date'].strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        self.doc['description'] = data['description']

        try:
            doc_type = self.grm_db.get_query_result({
                "id": int(data['issue_type']),
                "type": 'issue_type'
            })[0][0]
            doc_category = self.grm_db.get_query_result({
                "id": int(data['category']),
                "type": 'issue_category'
            })[0][0]
            department_id = doc_category['assigned_department']['id']
        except Exception:
            raise Http404

        self.doc['issue_type'] = {
            "id": doc_type['id'],
            "name": doc_type['name'],
        }
        self.doc['category'] = {
            "id": doc_category['id'],
            "name": doc_category['name'],
            "confidentiality_level": doc_category['confidentiality_level'],
            "assigned_department": department_id,
            "administrative_level": doc_category['assigned_department']['administrative_level'],
        }
        self.doc['ongoing_issue'] = data['ongoing_issue']

        self.doc.save()

    def set_person_fields(self, data):
        self.doc['citizen'] = data['citizen']

        citizen_type = int(data['citizen_type']) if data['citizen_type'] else None
        self.doc['citizen_type'] = citizen_type

        if data['citizen'] and not citizen_type:
            self.doc['citizen_type'] = 0

        if data['citizen_age_group']:
            try:
                doc_issue_age_group = self.grm_db.get_query_result({
                    "id": int(data['citizen_age_group']),
                    "type": 'issue_age_group'
                })[0][0]
                self.doc['citizen_age_group'] = {
                    "name": doc_issue_age_group['name'],
                    "id": doc_issue_age_group['id']
                }
            except Exception:
                raise Http404
        else:
            self.doc['citizen_age_group'] = ""

        self.doc['gender'] = data['gender']

        if data['citizen_group_1']:
            try:
                doc_issue_citizen_group_1 = self.grm_db.get_query_result({
                    "id": int(data['citizen_group_1']),
                    "type": 'issue_citizen_group_1'
                })[0][0]
                self.doc['citizen_group_1'] = {
                    "name": doc_issue_citizen_group_1['name'],
                    "id": doc_issue_citizen_group_1['id']
                }
            except Exception:
                raise Http404
        else:
            self.doc['citizen_group_1'] = ""

        if data['citizen_group_2']:
            try:
                doc_issue_citizen_group_2 = self.grm_db.get_query_result({
                    "id": int(data['citizen_group_2']),
                    "type": 'issue_citizen_group_2'
                })[0][0]
                self.doc['citizen_group_2'] = {
                    "name": doc_issue_citizen_group_2['name'],
                    "id": doc_issue_citizen_group_2['id']
                }
            except Exception:
                raise Http404
        else:
            self.doc['citizen_group_2'] = ""

    def set_location_fields(self, data):

        try:
            doc_administrative_level = self.eadl_db.get_query_result({
                "administrative_id": data['administrative_region_value'],
                "type": 'administrative_level'
            })[0][0]
        except Exception:
            raise Http404

        self.doc['administrative_region'] = {
            "administrative_id": doc_administrative_level['administrative_id'],
            "name": doc_administrative_level['name'],
        }

    def set_assignee(self):

        try:
            assignee = get_assignee(self.grm_db, self.eadl_db, self.doc)
        except Exception:
            raise Http404

        if assignee == "":
            msg = _("There is no staff member for the selected category (nature of the issue). "
                    "Please report to IT staff.")
            messages.add_message(self.request, messages.ERROR, msg, extra_tags='danger')

        self.doc['assignee'] = assignee

    def set_contact_fields(self, data):
        self.doc['contact_medium'] = data['contact_medium']
        if data['contact_medium'] == CHOICE_CONTACT:
            self.doc['contact_information'] = {
                "type": data['contact_type'],
                "contact": data['contact'],
            }
        else:
            self.doc['contact_information'] = None


class NewIssueContactFormView(PageMixin, NewIssueMixin):
    template_name = 'grm/new_issue_contact.html'
    title = _('GRM')
    active_level1 = 'grm'
    form_class = NewIssueContactForm

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            self.set_contact_fields(data)
        except Exception as e:
            raise e
        self.doc.save()
        return HttpResponseRedirect(reverse('dashboard:grm:new_issue_step_2', kwargs={'issue': self.kwargs['issue']}))


class NewIssuePersonFormView(PageMixin, NewIssueMixin):
    template_name = 'grm/new_issue_person.html'
    title = _('GRM')
    active_level1 = 'grm'
    form_class = NewIssuePersonForm
    fields_to_check = ('contact_medium',)

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            self.set_person_fields(data)
        except Exception as e:
            raise e
        self.doc.save()
        return HttpResponseRedirect(reverse('dashboard:grm:new_issue_step_3', kwargs={'issue': self.kwargs['issue']}))


class NewIssueDetailsFormView(PageMixin, NewIssueMixin):
    template_name = 'grm/new_issue_details.html'
    title = _('GRM')
    active_level1 = 'grm'
    form_class = NewIssueDetailsForm
    fields_to_check = ('contact_medium', 'citizen')

    def form_valid(self, form):
        data = form.cleaned_data
        self.set_details_fields(data)
        self.doc.save()
        return HttpResponseRedirect(reverse('dashboard:grm:new_issue_step_4', kwargs={'issue': self.kwargs['issue']}))


class NewIssueLocationFormView(PageMixin, NewIssueMixin):
    template_name = 'grm/new_issue_location.html'
    title = _('GRM')
    active_level1 = 'grm'
    form_class = NewIssueLocationForm
    fields_to_check = ('contact_medium', 'intake_date', 'issue_date', 'issue_type', 'category', 'description',
                       'ongoing_issue')

    def form_valid(self, form):
        data = form.cleaned_data
        self.set_location_fields(data)
        self.set_assignee()
        self.doc.save()
        return HttpResponseRedirect(reverse('dashboard:grm:new_issue_step_5', kwargs={'issue': self.kwargs['issue']}))


class NewIssueConfirmFormView(PageMixin, NewIssueMixin):
    template_name = 'grm/new_issue_confirm.html'
    title = _('GRM')
    active_level1 = 'grm'
    form_class = NewIssueConfirmForm
    fields_to_check = ('contact_medium', 'intake_date', 'issue_date', 'issue_type', 'category', 'description',
                       'ongoing_issue', 'assignee', 'administrative_region')

    def form_valid(self, form):
        if not self.doc['assignee']:
            return HttpResponseRedirect(
                reverse('dashboard:grm:new_issue_step_4', kwargs={'issue': self.kwargs['issue']}))
        data = form.cleaned_data
        try:
            self.set_contact_fields(data)
            self.set_person_fields(data)
            self.set_details_fields(data)
            self.set_location_fields(data)
            self.set_assignee()
        except Exception as e:
            raise e
        self.set_contact_fields(data)
        self.doc['confirmed'] = True
        try:
            doc_category = self.grm_db.get_query_result({
                "id": self.doc['category']['id'],
                "type": 'issue_category'
            })[0][0]
        except Exception:
            raise Http404
        administrative_id = self.doc["administrative_region"]["administrative_id"]
        self.doc[
            'internal_code'] = f'{doc_category["abbreviation"]}-{administrative_id}-{self.doc["auto_increment_id"]}'

        try:
            doc_status = self.grm_db.get_query_result({
                "open_status": True,
                "type": 'issue_status'
            })[0][0]
        except Exception:
            raise Http404
        self.doc['status'] = {
            "name": doc_status['name'],
            "id": doc_status['id']
        }

        self.doc['created_date'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        self.doc.save()
        return HttpResponseRedirect(reverse('dashboard:grm:new_issue_step_6', kwargs={'issue': self.kwargs['issue']}))


class NewIssueConfirmationFormView(PageMixin, NewIssueMixin):
    template_name = 'grm/new_issue_confirmation.html'
    title = _('GRM')
    active_level1 = 'grm'
    form_class = NewIssueConfirmForm
    permissions = ('read_only_by_reporter',)

    def get_query_result(self, **kwargs):
        return self.grm_db.get_query_result({
            "auto_increment_id": kwargs['issue'],
            "confirmed": True,
            "type": 'issue'
        })


class ReviewIssuesFormView(PageMixin, LoginRequiredMixin, generic.FormView):
    form_class = SearchIssueForm
    template_name = 'grm/review_issues.html'
    title = _('Review Issues')
    active_level1 = 'grm'
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:grm:dashboard'),
            'title': _('GRM')
        },
        {
            'url': '',
            'title': title
        }
    ]


class IssueListView(AJAXRequestMixin, LoginRequiredMixin, generic.ListView):
    template_name = 'grm/issue_list.html'
    context_object_name = 'issues'

    def get_queryset(self):
        grm_db = get_db(COUCHDB_GRM_DATABASE)
        eadl_db = get_db()
        index = int(self.request.GET.get('index'))
        offset = int(self.request.GET.get('offset'))
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        code = self.request.GET.get('code')
        assigned_to = self.request.GET.get('assigned_to')
        category = self.request.GET.get('category')
        issue_type = self.request.GET.get('type')
        status = self.request.GET.get('status')

        selector = {
            "type": "issue",
            "confirmed": True,
            "auto_increment_id": {"$ne": ""},
        }
        user = self.request.user
        if hasattr(user, 'governmentworker'):
            parent_id = user.governmentworker.administrative_level
            descendants = get_administrative_level_descendants(eadl_db, parent_id, [])
            allowed_regions = descendants + [parent_id]
            selector["$or"] = [
                {"assignee.id": user.id},
                {"$and": [
                    {"category.assigned_department": user.governmentworker.department},
                    {"administrative_region.administrative_id": {"$in": allowed_regions}},
                ]}
            ]

        date_range = dict()
        if start_date:
            start_date = datetime.strptime(start_date, '%d/%m/%Y').strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            date_range["$gte"] = start_date
            selector["intake_date"] = date_range
        if end_date:
            end_date = (datetime.strptime(end_date, '%d/%m/%Y') + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            date_range["$lte"] = end_date
            selector["intake_date"] = date_range
        if code:
            code_filter = {"$regex": f"^{code}"}
            selector['$or'] = [{"internal_code": code_filter}, {"tracking_code": code_filter}]
        if assigned_to:
            selector["assignee.id"] = int(assigned_to)
        if category:
            selector["category.id"] = int(category)
        if issue_type:
            selector["issue_type.id"] = int(issue_type)
        if status:
            selector["status.id"] = int(status)
        return grm_db.get_query_result(selector)[index:index + offset]


class IssueCommentsContextMixin:
    doc_department = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            self.doc_department = self.grm_db.get_query_result({
                "id": self.doc['category']['assigned_department'],
                "type": 'issue_department'
            })[0][0]
        except Exception:
            raise Http404
        context['colors'] = ['warning', 'mediumslateblue', 'gray', 'mediumpurple', 'plum', 'primary', 'danger']
        comments = self.doc['comments'] if 'comments' in self.doc else list()
        users = {c['id'] for c in comments} | {
            self.doc['assignee']['id'], self.doc_department['head']['id']}
        indexed_users = dict()
        for index, user_id in enumerate(users):
            indexed_users[user_id] = index
        context['indexed_users'] = indexed_users
        return context


class IssueDetailsFormView(PageMixin, IssueMixin, IssueCommentsContextMixin, LoginRequiredMixin, generic.FormView):
    form_class = IssueDetailsForm
    template_name = 'grm/issue_detail.html'
    title = _('Issue Detail')
    active_level1 = 'grm'
    breadcrumb = [
        {
            'url': reverse_lazy('dashboard:grm:dashboard'),
            'title': _('GRM')
        },
        {
            'url': reverse_lazy('dashboard:grm:review_issues'),
            'title': _('Review Issues')
        },
        {
            'url': '',
            'title': title
        }
    ]

    def get_form_kwargs(self):
        self.initial = {'doc_id': self.doc['_id']}
        return super().get_form_kwargs()

    def get_query_result(self, **kwargs):
        return self.grm_db.get_query_result({
            "auto_increment_id": kwargs['issue'],
            "confirmed": True,
            "type": 'issue'
        })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.request.user.id
        context['enable_add_comment'] = user_id == self.doc['assignee']['id'] or user_id == self.doc_department[
            'head']['id']
        context['comment_form'] = IssueCommentForm()
        try:
            doc_status = self.grm_db.get_query_result({
                "id": self.doc['status']['id'],
                "type": 'issue_status'
            })[0][0]
        except Exception:
            raise Http404
        context['doc_status'] = doc_status

        return context


class EditIssueView(IssueMixin, AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    permissions = ('read',)

    def post(self, request, *args, **kwargs):
        assignee = int(request.POST.get('assignee'))
        worker = GovernmentWorker.objects.get(user=assignee)
        self.doc['assignee'] = {
            "id": worker.user.id,
            "name": worker.name
        }
        self.doc.save()
        msg = _("The issue was successfully edited.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')
        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class AddCommentToIssueView(IssueMixin, AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):

    def post(self, request, *args, **kwargs):
        try:
            doc_department = self.grm_db.get_query_result({
                "id": self.doc['category']['assigned_department'],
                "type": 'issue_department'
            })[0][0]
        except Exception:
            raise Http404
        user_id = request.user.id
        if user_id != self.doc['assignee']['id'] and user_id != doc_department['head']['id']:
            raise PermissionDenied()

        comment = request.POST.get('comment').strip()[:MAX_LENGTH]
        if comment:
            comments = self.doc['comments'] if 'comments' in self.doc else list()
            comment_obj = {
                "name": request.user.name,
                "id": user_id,
                "comment": comment,
                "due_at": datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            }
            comments.insert(0, comment_obj)
            self.doc['comments'] = comments
            self.doc.save()
            msg = _("The comment was sent successfully.")
            messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')
        else:
            msg = _("Comment cannot be empty.")
            messages.add_message(self.request, messages.ERROR, msg, extra_tags='danger')
        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class IssueCommentListView(IssueMixin, IssueCommentsContextMixin, AJAXRequestMixin, LoginRequiredMixin,
                           generic.ListView):
    template_name = 'grm/issue_comments.html'
    context_object_name = 'comments'
    permissions = ('read',)

    def get_queryset(self):
        return self.doc['comments'] if 'comments' in self.doc else list()


class IssueStatusButtonsTemplateView(IssueMixin, AJAXRequestMixin, LoginRequiredMixin, generic.TemplateView):
    template_name = 'grm/issue_status_buttons.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            doc_status = self.grm_db.get_query_result({
                "id": self.doc['status']['id'],
                "type": 'issue_status'
            })[0][0]
        except Exception:
            raise Http404
        context['doc_status'] = doc_status

        return context


class SubmitIssueOpenStatusView(IssueMixin, AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    permissions = ('read',)

    def check_permissions(self):
        super().check_permissions()
        try:
            doc_status = self.grm_db.get_query_result({
                "id": self.doc["status"]["id"],
                "type": 'issue_status'
            })[0][0]
        except Exception:
            self.has_permission = False
            return

        open_status = doc_status['open_status'] if 'open_status' in doc_status else False
        initial_status = doc_status['initial_status'] if 'initial_status' in doc_status else False
        rejected_status = doc_status['rejected_status'] if 'rejected_status' in doc_status else False
        if open_status or not initial_status or rejected_status:
            self.has_permission = False

    def post(self, request, *args, **kwargs):
        self.doc['research_result'] = ""
        self.doc['reject_reason'] = ""
        try:
            doc_status = self.grm_db.get_query_result({
                "open_status": True,
                "type": 'issue_status'
            })[0][0]
        except Exception:
            raise Http404
        self.doc['status'] = {
            "name": doc_status['name'],
            "id": doc_status['id']
        }
        self.doc.save()
        msg = _("The issue status was successfully updated.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')
        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class SubmitIssueResearchResultFormView(AJAXRequestMixin, ModalFormMixin, LoginRequiredMixin, JSONResponseMixin,
                                        IssueFormMixin):
    form_class = IssueResearchResultForm
    id_form = "research_result_form"
    title = _('Please enter the resolution reached for this issue')
    submit_button = _('Save')
    permissions = ('read',)

    def check_permissions(self):
        super().check_permissions()
        try:
            doc_status = self.grm_db.get_query_result({
                "id": self.doc["status"]["id"],
                "type": 'issue_status'
            })[0][0]
        except Exception:
            self.has_permission = False
            return

        open_status = doc_status['open_status'] if 'open_status' in doc_status else False
        final_status = doc_status['final_status'] if 'final_status' in doc_status else False
        if final_status or not open_status:
            self.has_permission = False

    def form_valid(self, form):
        data = form.cleaned_data
        self.doc['research_result'] = data["research_result"]
        self.doc['reject_reason'] = ""
        try:
            doc_status = self.grm_db.get_query_result({
                "final_status": True,
                "type": 'issue_status'
            })[0][0]
        except Exception:
            raise Http404
        self.doc['status'] = {
            "name": doc_status['name'],
            "id": doc_status['id']
        }
        self.doc.save()
        msg = _("The issue status was successfully updated.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')

        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class SubmitIssueRejectReasonFormView(AJAXRequestMixin, ModalFormMixin, LoginRequiredMixin, JSONResponseMixin,
                                      IssueFormMixin):
    form_class = IssueRejectReasonForm
    id_form = "reject_reason_form"
    title = _('Enter the reason for rejecting this issue')
    submit_button = _('Save')
    permissions = ('read',)

    def check_permissions(self):
        super().check_permissions()
        try:
            doc_status = self.grm_db.get_query_result({
                "id": self.doc["status"]["id"],
                "type": 'issue_status'
            })[0][0]
        except Exception:
            self.has_permission = False
            return

        initial_status = doc_status['initial_status'] if 'initial_status' in doc_status else False
        rejected_status = doc_status['rejected_status'] if 'rejected_status' in doc_status else False
        if rejected_status or not initial_status:
            self.has_permission = False

    def form_valid(self, form):
        data = form.cleaned_data
        self.doc['reject_reason'] = data["reject_reason"]
        self.doc['research_result'] = ""
        try:
            doc_status = self.grm_db.get_query_result({
                "rejected_status": True,
                "type": 'issue_status'
            })[0][0]
        except Exception:
            raise Http404
        self.doc['status'] = {
            "name": doc_status['name'],
            "id": doc_status['id']
        }
        self.doc.save()
        msg = _("The issue status was successfully updated.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags='success')

        context = {'msg': render(self.request, 'common/messages.html').content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class GetChoicesForNextAdministrativeLevelView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        parent_id = request.GET.get('parent_id')
        eadl_db = get_db()
        data = get_child_administrative_levels(eadl_db, parent_id)
        return self.render_to_json_response(data, safe=False)


class GetAncestorAdministrativeLevelsView(AJAXRequestMixin, LoginRequiredMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        administrative_id = request.GET.get('administrative_id', None)
        ancestors = list()
        if administrative_id:
            eadl_db = get_db()
            has_parent = True
            while has_parent:
                parent = get_parent_administrative_level(eadl_db, administrative_id)
                if parent:
                    administrative_id = parent['administrative_id']
                    ancestors.insert(0, administrative_id)
                else:
                    has_parent = False
        return self.render_to_json_response(ancestors, safe=False)
