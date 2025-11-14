import random
from datetime import datetime, timedelta

import cryptocode
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views import generic

from authentication.models import Cdata, GovernmentWorker, Pdata
from common.utils.forms import FileForm
from dashboard.grm.forms import (
    IssueCommentForm,
    IssueDetailsForm,
    IssueRejectReasonForm,
    IssueResearchResultForm,
    NewIssueConfirmationForm,
    NewIssueConfirmForm,
    NewIssueContactForm,
    NewIssueDetailsForm,
    NewIssueLocationForm,
    NewIssuePersonForm,
    SearchIssueForm,
)
from dashboard.grm.permissions import reporter_can_access_issue, user_can_access_issue
from dashboard.mixins import (
    JSONResponseMixin,
    LoginRequiredAndAJAXRequestMixin,
    ModalFormMixin,
    PageMixin,
)
from dashboard.user_management.forms import PasswordConfirmForm
from grm.constants import (
    ALERT_CHOICE,
    CONFIDENTIAL_CHOICE,
    EMPTY_COMMENT_ERROR_MESSAGE,
    MAX_ATTACHMENTS,
    TEXTAREA_MAX_LENGTH,
)
from grm.utils import get_issue_select_options_choices
from issues.models import (
    AdministrativeRegion,
    Citizen,
    Comment,
    Issue,
    IssueAttachment,
    IssueStatus,
)

COUCHDB_GRM_DATABASE = settings.COUCHDB_GRM_DATABASE
COUCHDB_GRM_ATTACHMENT_DATABASE = settings.COUCHDB_GRM_ATTACHMENT_DATABASE


class DashboardTemplateView(PageMixin, LoginRequiredMixin, generic.TemplateView):
    """Dashboard main view. Accessible by GRM Manager and Case Manager."""

    template_name = "grm/dashboard.html"
    title = _("GRM")
    active_level1 = "grm"
    breadcrumb = [
        {"url": "", "title": title},
    ]

    def dispatch(self, request, *args, **kwargs):
        # Only GRM Manager and Case Manager can access dashboard
        if not request.user.grm_manager and not hasattr(request.user, 'governmentworker'):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class StartNewIssueView(LoginRequiredMixin, generic.View):
    """Start creating a new issue. Accessible by GRM Manager and Case Manager."""

    def dispatch(self, request, *args, **kwargs):
        # Only GRM Manager and Case Manager can create issues
        if not request.user.grm_manager and not hasattr(request.user, 'governmentworker'):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        user = request.user
        sample_words = ["Tree", "Cat", "Dog", "Car", "House"]
        initial_status = IssueStatus.objects.get(initial_status=True)
        issue = Issue.objects.create(
            reporter=user,
            tracking_code=f"{random.choice(sample_words)}{random.choice(range(1, 1000))}",
            status=initial_status,
        )
        return HttpResponseRedirect(
            reverse(
                "dashboard:grm:new_issue_step_1",
                kwargs={"issue": issue.id},
            )
        )


class IssueMixin:
    """
    Base mixin for views that work with a specific Issue.

    By default, requires user to have access permission (GRM Manager or PIU staff).
    Override check_permissions() in subclasses for custom permission logic.
    """

    obj = None

    def get_query_result(self, **kwargs):
        return Issue.objects.select_related('reporter', 'administrative_region', 'assignee')

    def check_permissions(self):
        """Check if user has permission to access this issue."""
        if not self.obj:
            raise Http404

        if not user_can_access_issue(self.request.user, self.obj):
            raise PermissionDenied

    def dispatch(self, request, *args, **kwargs):
        self.obj = self.get_query_result(**kwargs).filter(id=kwargs["issue"]).first()
        self.check_permissions()
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["obj"] = self.obj
        context["max_attachments"] = MAX_ATTACHMENTS
        context["choice_contact"] = ALERT_CHOICE
        return context


class UploadIssueAttachmentFormView(
    IssueMixin,
    LoginRequiredAndAJAXRequestMixin,
    ModalFormMixin,
    JSONResponseMixin,
    generic.FormView,
):
    """
    Upload attachment to an issue.

    Permissions:
    - If issue unconfirmed: Only reporter can upload
    - If issue confirmed: GRM Manager or PIU staff can upload
    """

    form_class = FileForm
    title = _("Add attachment")
    submit_button = _("Upload")

    def form_valid(self, form):
        data = form.cleaned_data
        attachments = IssueAttachment.objects.filter(issue=self.obj)
        if len(attachments) < MAX_ATTACHMENTS:
            user = self.request.user
            try:
                IssueAttachment.objects.create(issue=self.obj, file=data["file"], uploaded_by=user)

                # Add a comment relative to the action: Add new attachment to the issue.
                comment = _("A new attachment %s has been added to the issue.") % data["file"].name
                Comment.objects.create(user=user, comment=comment, issue=self.obj)
                msg = _("The attachment was successfully uploaded.")
                messages.add_message(self.request, messages.SUCCESS, msg, extra_tags="success")
            except Exception:
                msg = _(
                    "An error has occurred that did not allow the attachment to be uploaded to the database. "
                    "Please report to IT staff."
                )
                messages.add_message(self.request, messages.ERROR, msg, extra_tags="danger")
        else:
            msg = _(
                "The file could not be uploaded because it has already reached the limit of %(max)d attachments."
            ) % {"max": MAX_ATTACHMENTS}
            messages.add_message(self.request, messages.ERROR, msg, extra_tags="danger")
        context = {"msg": render(self.request, "common/messages.html").content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class IssueAttachmentDeleteView(
    IssueMixin, LoginRequiredAndAJAXRequestMixin, ModalFormMixin, JSONResponseMixin, generic.View
):
    """
    Delete attachment from an issue.

    Permissions:
    - If issue unconfirmed: Only reporter can delete
    - If issue confirmed: GRM Manager or PIU staff can delete
    """

    def post(self, request, *args, **kwargs):
        attachment = IssueAttachment.objects.filter(id=kwargs["attachment"]).first()
        if attachment:
            attachment_name = attachment.filename
            attachment.delete()

            # Add a comment relative to the action: Attachment deletion
            comment = _("The attachment %s has been deleted to the issue.") % attachment_name
            Comment.objects.create(user=request.user, comment=comment, issue=self.obj)

        msg = _("The attachment was successfully deleted.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags="success")
        context = {"msg": render(self.request, "common/messages.html").content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class IssueAttachmentListView(IssueMixin, LoginRequiredAndAJAXRequestMixin, generic.ListView):
    """
    List attachments for an issue.

    Permissions:
    - If issue unconfirmed: Only reporter can view
    - If issue confirmed: GRM Manager or PIU staff can view
    """

    template_name = "grm/issue_attachments.html"
    context_object_name = "attachments"

    def get_queryset(self):
        return IssueAttachment.objects.filter(issue=self.obj)

    def dispatch(self, request, *args, **kwargs):
        column = self.request.GET.get("column", "")
        if column:
            self.template_name = "grm/issue_attachments_column1.html"
        return super().dispatch(request, *args, **kwargs)


class IssueFormMixin(IssueMixin, generic.FormView):
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.obj
        return kwargs


class NewIssueMixin(PageMixin, LoginRequiredMixin, IssueFormMixin):
    """
    Mixin for views that handle issue creation process.

    Permissions: Only the reporter can access their unconfirmed issues.
    The filter in get_query_result ensures only the reporter can access their own issue.
    """

    title = _("GRM")
    active_level1 = "grm"
    breadcrumb = [
        {"url": reverse_lazy("dashboard:grm:dashboard"), "title": _("GRM")},
        {"url": "", "title": _("Enter New Issue")},
    ]
    fields_to_check = None

    def dispatch(self, request, *args, **kwargs):
        # Only GRM Manager and Case Manager can create issues
        if not request.user.grm_manager and not hasattr(request.user, 'governmentworker'):
            raise PermissionDenied

        dispatch = super().dispatch(request, *args, **kwargs)
        if not self.has_required_fields():
            raise Http404
        return dispatch

    def get_query_result(self, **kwargs):
        # Only the reporter can access their unconfirmed issues
        return Issue.objects.filter(id=kwargs["issue"], reporter=self.request.user, confirmed=False).select_related(
            'administrative_region',
            'assignee',
            'category',
            'citizen__group',
            'citizen__age_group',
            'component',
            'issue_type',
            'issue_sub_type',
            'reporter',
            'subproject_group',
            'sub_component',
        )

    def has_required_fields(self):
        if self.fields_to_check and self.obj:
            for field in self.fields_to_check:
                if getattr(self.obj, field) in [None, ""]:
                    return False
        return True

    def set_details_fields(self, data):
        self.obj.intake_date = data["intake_date"]
        self.obj.issue_date = data["issue_date"]
        self.obj.issue_type_id = int(data["issue_type"])
        self.obj.issue_sub_type = data["issue_sub_type"]
        self.obj.category = data["category"]
        self.obj.component_id = int(data["component"]) if data["component"] else None
        self.obj.sub_component = data["sub_component"] if data["sub_component"] else None
        self.obj.subproject_group_id = int(data["subproject_group"]) if data["subproject_group"] else None
        self.obj.description = data["description"]
        self.obj.ongoing_issue = data["ongoing_issue"]

    def set_person_fields(self, data):
        citizen_name = data["citizen"].strip()
        citizen_type = data["citizen_type"]
        citizen_age_group = data["citizen_age_group"]
        gender = data["gender"]
        citizen_group = data["citizen_group"]
        values = [citizen_name, citizen_type, citizen_age_group, gender, citizen_group]
        citizen = self.obj.citizen
        if any(v not in (None, "") for v in values):
            if citizen:
                citizen.name = citizen_name
            else:
                citizen = Citizen(name=citizen_name)
                self.obj.citizen = citizen

            citizen.type = data["citizen_type"] if data["citizen_type"] else None

            citizen.age_group_id = int(data["citizen_age_group"]) if data["citizen_age_group"] else ""

            citizen.gender = data["gender"]

            citizen.group_id = int(data["citizen_group"]) if data["citizen_group"] else ""
            citizen.save()
        else:
            if citizen:
                self.obj.citizen = None
                return citizen

    def set_location_fields(self, data):
        self.obj.administrative_region = data["administrative_region"]
        self.obj.location_description = data["location_description"]

    def set_assignee(self):
        assignee = self.obj.get_assignee()
        self.obj.assignee = assignee

        if not assignee:
            msg = _("No staff member was found to assign the issue to. The issue will be created without an assignee.")
            messages.add_message(self.request, messages.WARNING, msg, extra_tags="warning")

    def set_contact_fields(self, data):
        self.obj.contact_medium = data["contact_medium"]
        if data["contact_medium"] == ALERT_CHOICE:
            self.obj.contact_information = data["contact"]
            self.obj.contact_method = data["contact_type"]
        else:
            self.obj.contact_information = None
            self.obj.contact_method = None


class NewIssueContactFormView(NewIssueMixin):
    template_name = "grm/new_issue_contact.html"
    form_class = NewIssueContactForm

    def form_valid(self, form):
        data = form.cleaned_data
        self.set_contact_fields(data)
        try:
            self.obj.save()
        except ValidationError as e:
            messages.add_message(self.request, messages.ERROR, e.message, extra_tags="danger")
            return HttpResponseRedirect(
                reverse(
                    "dashboard:grm:new_issue_step_1",
                    kwargs={"issue": self.kwargs["issue"]},
                )
            )

        return HttpResponseRedirect(reverse("dashboard:grm:new_issue_step_2", kwargs={"issue": self.kwargs["issue"]}))


class NewIssuePersonFormView(NewIssueMixin):
    template_name = "grm/new_issue_person.html"
    form_class = NewIssuePersonForm
    fields_to_check = ("contact_medium",)

    def form_valid(self, form):
        data = form.cleaned_data
        try:
            citizen_to_delete = self.set_person_fields(data)
            self.obj.save()
            if citizen_to_delete:
                citizen_to_delete.delete()
        except Exception as e:
            raise e
        return HttpResponseRedirect(reverse("dashboard:grm:new_issue_step_3", kwargs={"issue": self.kwargs["issue"]}))


class NewIssueDetailsFormView(NewIssueMixin):
    template_name = "grm/new_issue_details.html"
    form_class = NewIssueDetailsForm
    fields_to_check = ("contact_medium",)

    def has_required_fields(self):
        if self.obj.citizen and self.obj.citizen.name and not self.obj.citizen.type:
            return False
        return super().has_required_fields()

    def form_valid(self, form):
        data = form.cleaned_data
        self.set_details_fields(data)
        self.obj.save()
        return HttpResponseRedirect(reverse("dashboard:grm:new_issue_step_4", kwargs={"issue": self.kwargs["issue"]}))


class NewIssueLocationFormView(NewIssueMixin):
    template_name = "grm/new_issue_location.html"
    form_class = NewIssueLocationForm
    fields_to_check = (
        "contact_medium",
        "intake_date",
        "issue_date",
        "issue_type",
        "category",
        "description",
        "ongoing_issue",
        "issue_sub_type",
    )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass government_worker id if user is a Case Manager
        if hasattr(self.request.user, 'governmentworker'):
            context['government_worker_id'] = self.request.user.governmentworker.id
        else:
            context['government_worker_id'] = None
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        self.set_location_fields(data)
        self.set_assignee()
        self.obj.save()
        # Remove the if not self.obj.assignee check - allow proceeding without assignee
        return HttpResponseRedirect(reverse("dashboard:grm:new_issue_step_5", kwargs={"issue": self.kwargs["issue"]}))


class NewIssueConfirmFormView(NewIssueMixin):
    template_name = "grm/new_issue_confirm.html"
    form_class = NewIssueConfirmForm
    fields_to_check = (
        "contact_medium",
        "intake_date",
        "issue_date",
        "issue_type",
        "category",
        "description",
        "ongoing_issue",
        "administrative_region",
        "issue_sub_type",
    )

    def form_valid(self, form):
        data = form.cleaned_data
        self.set_contact_fields(data)
        citizen_to_delete = self.set_person_fields(data)
        self.set_details_fields(data)
        self.set_location_fields(data)
        self.set_assignee()

        # Remove the if not self.obj.assignee check - allow proceeding without assignee

        self.set_contact_fields(data)
        self.obj.internal_code = self.obj.get_internal_code()
        self.obj.confirmed = True
        self.obj.anonymize_issue_data()
        self.obj.save()
        if citizen_to_delete:
            citizen_to_delete.delete()
        return HttpResponseRedirect(reverse("dashboard:grm:new_issue_step_6", kwargs={"issue": self.kwargs["issue"]}))


class NewIssueConfirmationFormView(NewIssueMixin):
    template_name = "grm/new_issue_confirmation.html"
    form_class = NewIssueConfirmationForm

    def check_permissions(self):
        """Check if user has permission to access this issue."""
        if not self.obj:
            raise Http404

        if not reporter_can_access_issue(self.request.user, self.obj):
            raise PermissionDenied

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.pop('obj')
        return kwargs

    def get_query_result(self, **kwargs):
        return (
            Issue.objects.filter(id=kwargs["issue"], confirmed=True)
            .select_related(
                'administrative_region',
                'assignee',
                'category',
                'citizen__group',
                'citizen__age_group',
                'component',
                'issue_type',
                'issue_sub_type',
                'reporter',
                'subproject_group',
                'sub_component',
            )
            .prefetch_related("attachments")
        )


class ReviewIssuesFormView(PageMixin, LoginRequiredMixin, generic.FormView):
    form_class = SearchIssueForm
    template_name = "grm/review_issues.html"
    title = _("Review Issues")
    active_level1 = "grm"
    breadcrumb = [
        {"url": reverse_lazy("dashboard:grm:dashboard"), "title": _("GRM")},
        {"url": "", "title": title},
    ]


class IssueListView(LoginRequiredAndAJAXRequestMixin, JSONResponseMixin, generic.View):
    template_name = "grm/issue_list.html"
    context_object_name = "issues"

    def get(self, request, *args, **kwargs):

        offset = int(self.request.GET.get("offset", 10))
        cursor_date = self.request.GET.get("cursor_date")
        cursor_id = self.request.GET.get("cursor_id")
        direction = request.GET.get("direction", "next")
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")
        code = self.request.GET.get("code")
        assigned_to = self.request.GET.get("assigned_to")
        category = self.request.GET.get("category")
        issue_type = self.request.GET.get("type")
        status = self.request.GET.get("status")

        and_filters = [{"confirmed": True}]

        if start_date:
            start_date = datetime.strptime(start_date, "%d/%m/%Y").strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            and_filters.append({"intake_date__gte": start_date})
        if end_date:
            end_date = (datetime.strptime(end_date, "%d/%m/%Y") + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            and_filters.append({"intake_date__lte": end_date})
        if assigned_to:
            and_filters.append({"assignee": int(assigned_to)})
        if category:
            and_filters.append({"category": int(category)})
        if issue_type:
            and_filters.append({"issue_type": int(issue_type)})
        if status:
            and_filters.append({"status": int(status)})

        or_filters = []

        user = self.request.user
        head_q = Q()
        if hasattr(user, "governmentworker"):
            worker = user.governmentworker
            dept = worker.department
            is_head = getattr(dept, "head_id", None) == user.id

            # Always allow if the user is the assignee
            or_filters.append({"assignee": user})

            # If head, apply BOTH conditions (category assigned to dept AND region in hierarchy)
            if is_head:
                head_q = Q(category__assigned_department__department=dept) & Q(
                    administrative_region__in=worker.administrative_region.get_descendant_ids()
                )
        if code:
            or_filters += [
                {"internal_code__icontains": code},
                {"tracking_code__icontains": code},
            ]

        and_query = Q()
        for f in and_filters:
            and_query &= Q(**f)

        or_query = Q()
        for f in or_filters:
            or_query |= Q(**f)

        # Combine with head rule clause (AND inside, OR with other parts)
        or_query |= head_q

        final_query = and_query & or_query

        qs = Issue.objects.filter(final_query).order_by('-intake_date', '-id')

        if cursor_date and cursor_id:
            cursor_date_dt = datetime.fromisoformat(cursor_date)
            cursor_id = int(cursor_id)
            if direction == "next":
                qs = qs.filter(Q(intake_date__lt=cursor_date_dt) | Q(intake_date=cursor_date_dt, id__lt=cursor_id))
            elif direction == "previous":
                qs = qs.filter(
                    Q(intake_date__gt=cursor_date_dt) | Q(intake_date=cursor_date_dt, id__gt=cursor_id)
                ).order_by("intake_date", "id")

        results = list(qs[: offset + 1])
        page_results = results[:offset]
        has_more_forward = False
        if page_results:
            remaining_qs = qs.filter(
                Q(intake_date__lt=page_results[-1].intake_date)
                | Q(intake_date=page_results[-1].intake_date, id__lt=page_results[-1].id)
            ).exists()
            has_more_forward = remaining_qs

        if direction == "previous":
            page_results = list(reversed(page_results))

        first_issue = page_results[0] if page_results else None
        last_issue = page_results[-1] if page_results else None

        issues_html = render(request, "grm/issue_list.html", {"issues": page_results}).content.decode("utf-8")

        context = {
            "html": issues_html,
            "has_more_forward": has_more_forward,
            "next_cursor_date": last_issue.intake_date.isoformat() if last_issue else None,
            "next_cursor_id": last_issue.id if last_issue else None,
            "prev_cursor_date": first_issue.intake_date.isoformat() if first_issue else None,
            "prev_cursor_id": first_issue.id if first_issue else None,
        }

        return self.render_to_json_response(context, safe=False)


class IssueCommentsContextMixin:

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            department = self.obj.category.assigned_department.department
        except Exception:
            raise Http404
        context["colors"] = [
            "warning",
            "mediumslateblue",
            "gray",
            "mediumpurple",
            "plum",
            "primary",
            "danger",
        ]
        if not department.head:
            msg = _(f"There is no head member for '{department.name}'. Please report to IT staff.")
            messages.add_message(self.request, messages.ERROR, msg, extra_tags="danger")

        return context


class IssueDetailsFormView(
    PageMixin,
    IssueMixin,
    IssueCommentsContextMixin,
    LoginRequiredMixin,
    generic.FormView,
):
    form_class = IssueDetailsForm
    template_name = "grm/issue_detail.html"
    title = _("Issue Detail")
    active_level1 = "grm"
    breadcrumb = [
        {"url": reverse_lazy("dashboard:grm:dashboard"), "title": _("GRM")},
        {
            "url": reverse_lazy("dashboard:grm:review_issues"),
            "title": _("Review Issues"),
        },
        {"url": "", "title": title},
    ]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['obj'] = self.obj
        return kwargs

    def get_query_result(self, **kwargs):
        return Issue.objects.filter(id=kwargs["issue"], confirmed=True)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["enable_add_comment"] = self.obj.is_piu_staff(user) or user.grm_manager

        context["comment_form"] = IssueCommentForm()
        context["password_confirm_form"] = PasswordConfirmForm()
        context["comments"] = self.obj.comments.select_related('user')
        citizen_type = self.obj.citizen.type if self.obj.citizen else None
        # Handle case where assignee might be None
        context["confidential"] = (
            self.obj.assignee and self.obj.assignee.id != user.id and citizen_type == CONFIDENTIAL_CHOICE
        )

        return context


class EditIssueView(IssueMixin, LoginRequiredAndAJAXRequestMixin, JSONResponseMixin, generic.View):
    """Edit issue (assign/reassign). Permissions: GRM Manager or PIU staff."""

    def post(self, request, *args, **kwargs):
        assignee = int(request.POST.get("assignee"))
        worker = get_object_or_404(GovernmentWorker, user=assignee)
        self.obj.assignee = worker.user
        self.obj.save()
        msg = _("The issue was successfully edited.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags="success")
        context = {"msg": render(self.request, "common/messages.html").content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class AddCommentToIssueView(IssueMixin, LoginRequiredAndAJAXRequestMixin, JSONResponseMixin, generic.View):
    """Add comment to an issue. Permissions: GRM Manager or PIU staff."""

    def post(self, request, *args, **kwargs):
        user = request.user

        comment = request.POST.get("comment").strip()[:TEXTAREA_MAX_LENGTH]
        if comment:
            Comment.objects.create(user=user, comment=comment, issue=self.obj)
            msg = _("The comment was sent successfully.")
            messages.add_message(self.request, messages.SUCCESS, msg, extra_tags="success")
        else:
            msg = EMPTY_COMMENT_ERROR_MESSAGE
            messages.add_message(self.request, messages.ERROR, msg, extra_tags="danger")
        context = {"msg": render(self.request, "common/messages.html").content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class IssueCommentListView(
    IssueMixin,
    IssueCommentsContextMixin,
    LoginRequiredAndAJAXRequestMixin,
    generic.ListView,
):
    """List comments for an issue. Permissions: GRM Manager or PIU staff."""

    template_name = "grm/issue_comments.html"
    context_object_name = "comments"

    def get_queryset(self):
        return self.obj.comments.select_related("user")


class IssueStatusButtonsTemplateView(IssueMixin, LoginRequiredAndAJAXRequestMixin, generic.TemplateView):
    """Show issue status buttons. Permissions: GRM Manager or PIU staff."""

    template_name = "grm/issue_status_buttons.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["status"] = self.obj.status

        return context


class SubmitIssueOpenStatusView(IssueMixin, LoginRequiredAndAJAXRequestMixin, JSONResponseMixin, generic.View):
    """Change issue status to open. Permissions: GRM Manager or PIU staff."""

    def check_permissions(self):
        """Override to add status validation."""
        super().check_permissions()
        status = self.obj.status
        if status.open_status or not status.initial_status or status.rejected_status:
            raise PermissionDenied

    def post(self, request, *args, **kwargs):
        self.obj.research_result = ""
        self.obj.reject_reason = ""
        self.obj.status = IssueStatus.objects.get(open_status=True)
        self.obj.save()
        msg = _("The issue status was successfully updated.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags="success")
        context = {"msg": render(self.request, "common/messages.html").content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class SubmitIssueResearchResultFormView(
    LoginRequiredAndAJAXRequestMixin,
    ModalFormMixin,
    JSONResponseMixin,
    IssueFormMixin,
):
    """
    Submit resolution for an issue.

    Permissions: GRM Manager or PIU staff (via IssueMixin)
    Additional check: Issue status must be open (not final_status)
    """

    form_class = IssueResearchResultForm
    id_form = "research_result_form"
    title = _("Please enter the resolution reached for this issue")
    submit_button = _("Save")

    def check_permissions(self):
        """Override to add status validation."""
        super().check_permissions()
        status = self.obj.status
        if status.final_status or not status.open_status:
            raise PermissionDenied

    def form_valid(self, form):
        data = form.cleaned_data
        self.obj.research_result = data["research_result"]
        self.obj.reject_reason = ""
        self.obj.status = IssueStatus.objects.get(final_status=True)
        self.obj.save()

        Comment.objects.create(user=self.request.user, comment=_("The complaint has been resolved"), issue=self.obj)

        msg = _("The issue status was successfully updated.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags="success")

        context = {"msg": render(self.request, "common/messages.html").content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class SubmitIssueRejectReasonFormView(
    LoginRequiredAndAJAXRequestMixin,
    ModalFormMixin,
    JSONResponseMixin,
    IssueFormMixin,
):
    form_class = IssueRejectReasonForm
    id_form = "reject_reason_form"
    title = _("Enter the reason for rejecting this issue")
    submit_button = _("Save")

    def check_permissions(self):
        """Override to add status validation."""
        super().check_permissions()
        status = self.obj.status
        if status.rejected_status or not status.initial_status:
            raise PermissionDenied

    def form_valid(self, form):
        data = form.cleaned_data
        self.obj.reject_reason = data["reject_reason"]
        self.obj.research_result = ""
        self.obj.status = IssueStatus.objects.get(rejected_status=True)
        self.obj.save()

        Comment.objects.create(user=self.request.user, comment=_("The complaint has been rejected"), issue=self.obj)

        msg = _("The issue status was successfully updated.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags="success")

        context = {"msg": render(self.request, "common/messages.html").content.decode("utf-8")}
        return self.render_to_json_response(context, safe=False)


class GetChoicesForOptionView(LoginRequiredAndAJAXRequestMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        model_class = request.GET.get("model_class")
        parent_id = int(request.GET.get("parent_id"))
        data = get_issue_select_options_choices(model_class, parent_id)
        return render(self.request, "common/options.html", {"values": data})


class GetChoicesForNextAdministrativeLevelView(LoginRequiredAndAJAXRequestMixin, JSONResponseMixin, generic.View):
    """
    Get choices for next administrative level (children of a region).

    Optional: Filter by GovernmentWorker's allowed regions.
    """

    def get(self, request, *args, **kwargs):
        region = get_object_or_404(AdministrativeRegion, id=request.GET.get("parent_id"))
        exclude_lower_level = request.GET.get("exclude_lower_level", None)
        government_worker_id = request.GET.get("government_worker", None)

        children = region.children.all()

        # Filter by GovernmentWorker's administrative region family if provided
        if government_worker_id:
            try:
                worker = GovernmentWorker.objects.get(id=government_worker_id)
                if worker.administrative_region:
                    # Get allowed region IDs (worker's region, its ancestors and descendants)
                    ancestors = region.get_full_hierarchy_ids()
                    descendants = worker.administrative_region.get_descendant_ids()
                    allowed_region_ids = ancestors + descendants
                    # Filter children to only those in the allowed regions
                    children = children.filter(id__in=allowed_region_ids)
            except GovernmentWorker.DoesNotExist:
                pass

        data = list(children.values("id", "name", "administrative_level__name"))

        if children and exclude_lower_level and not children[0].children.exists():
            data = []

        return self.render_to_json_response(data, safe=False)


class GetAncestorAdministrativeLevelsView(LoginRequiredAndAJAXRequestMixin, JSONResponseMixin, generic.View):
    """
    View that returns the ancestor administrative levels for a given region.

    - Requires the request to be authenticated and AJAX (via LoginRequiredAndAJAXRequestMixin).
    - Accepts a GET parameter `region_id` identifying the region.
    - Looks up the region and retrieves its full hierarchy of IDs using
      `get_full_hierarchy_ids()`.
    - Excludes the root region from the result (by slicing [1:]).
    - Responds with a JSON array of ancestor IDs.
    """

    def get(self, request, *args, **kwargs):
        region_id = request.GET.get("region_id")
        ancestors = []
        if region_id:
            region = get_object_or_404(AdministrativeRegion, id=region_id)
            ancestors = region.get_full_hierarchy_ids()[1:]
        return self.render_to_json_response(ancestors, safe=False)


class GetSensitiveIssueDataView(LoginRequiredAndAJAXRequestMixin, JSONResponseMixin, generic.View):
    """
    Get sensitive/confidential data for an issue.

    Permissions: Only Case Manager AND must be assigned to the issue.
    """

    def dispatch(self, request, *args, **kwargs):
        # Only Case Managers can access sensitive data
        if not hasattr(request.user, 'governmentworker'):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        context = {
            "data": None,
        }

        if self.request.user.check_password(request.POST.get("password")):
            issue_id = request.POST.get("id")

            # Verify user is assignee of the issue
            issue = Issue.objects.filter(id=issue_id).first()
            if not issue or issue.assignee_id != request.user.id:
                raise PermissionDenied

            citizen = Pdata.objects.get(key=issue_id) if Pdata.objects.filter(key=issue_id).exists() else None
            citizen = cryptocode.decrypt(citizen.data, issue_id) if citizen else None

            contact = Cdata.objects.get(key=issue_id) if Cdata.objects.filter(key=issue_id).exists() else None
            contact = cryptocode.decrypt(contact.data, issue_id) if contact else None

            context["data"] = {
                "citizen": citizen,
                "contact": contact,
            }

        else:
            msg = _("The password was not correct, we could not proceed with action.")
            messages.add_message(self.request, messages.ERROR, msg, extra_tags="danger")
            context["msg"] = render(self.request, "common/messages.html").content.decode("utf-8")

        return self.render_to_json_response(context, safe=False)


class GetRegionChoicesForSelect2View(LoginRequiredAndAJAXRequestMixin, JSONResponseMixin, generic.View):
    def get(self, request, *args, **kwargs):
        query = request.GET.get('q')
        selected_id = request.GET.get('id')
        base_regions = request.GET.get('base_regions')
        with_issues = request.GET.get('with_issues')

        qs = AdministrativeRegion.objects.all().select_related('administrative_level')

        if selected_id:
            qs = qs.filter(id=selected_id)
        elif query:
            qs = qs.filter(hierarchical_name__istartswith=query)

        if base_regions:
            qs = qs.exclude(children__isnull=False)

        if with_issues:
            qs = qs.exclude(issues__isnull=True)

        results = [{'id': item.id, 'text': str(item)} for item in qs[:10]]
        return self.render_to_json_response(results, safe=False)
