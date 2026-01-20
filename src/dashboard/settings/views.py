from django.contrib import messages
from django.http.response import JsonResponse
from django.shortcuts import render
from django.urls.base import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic.base import TemplateView
from django.views.generic.edit import FormView

from dashboard.mixins import (
    PageMixin,
    UserManagementAndAJAXMixin,
    UserManagementPermissionMixin,
)
from issues.models import IssueStatus
from wizard.forms import ISSUE_STATUS_DEFINITIONS, ExistingIssueStatusFormSet


class SettingsTemplateView(PageMixin, UserManagementPermissionMixin, TemplateView):
    template_name = "settings/main.html"
    title = _("Settings")
    active_level1 = "settings"
    breadcrumb = [
        {"url": "", "title": title},
    ]


class SettingsByIssueStatusFormView(UserManagementAndAJAXMixin, FormView):
    form_class = ExistingIssueStatusFormSet
    template_name = "settings/static_formset.html"
    success_url = reverse_lazy("dashboard:settings:by_status")

    def get_form(self, form_class=None):
        queryset = IssueStatus.objects.all()
        return self.form_class(queryset=queryset, **self.get_form_kwargs())

    def form_valid(self, formset):
        instances = formset.save(commit=False)

        for instance, flag in zip(instances, ISSUE_STATUS_DEFINITIONS.keys()):
            if not instance.pk:
                instance.initial_status = flag == "initial_status"
                instance.open_status = flag == "open_status"
                instance.final_status = flag == "final_status"
                instance.rejected_status = flag == "rejected_status"
            instance.save()

        msg = _("The status settings was successfully updated.")
        messages.add_message(self.request, messages.SUCCESS, msg, extra_tags="success")

        context = {
            "msg": render(self.request, "common/messages.html").content.decode("utf-8"),
        }
        return JsonResponse(context, safe=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = context['form']  # Aliases for clarity in the template
        context['card_title'] = _("Settings by Issue Status")
        return context
