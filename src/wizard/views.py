from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Exists, OuterRef
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import FormView, ListView, TemplateView, UpdateView

from dashboard.mixins import AJAXRequestMixin
from dashboard.models import Project
from grm.constants import COMPLETED_CHOICE, IN_PROGRESS_CHOICE, NOT_STARTED_CHOICE
from issues.models import AdministrativeLevel, Issue, IssueDepartmentAdministrativeLevel
from wizard.forms import AdministrativeLevelFormSet, ProjectForm
from wizard.models import WizardSection


class CustomizationWizardView(LoginRequiredMixin, TemplateView):
    template_name = "wizard/grm_customization.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sections = list(WizardSection.objects.values_list('id', flat=True))
        total_steps = len(sections)
        context['total_steps'] = total_steps
        in_progress_section = WizardSection.objects.filter(status=IN_PROGRESS_CHOICE).first()
        ips_id = in_progress_section.id if in_progress_section else None
        context['current_step'] = sections.index(ips_id) + 1 if ips_id else total_steps
        return context


class WizardSectionListView(AJAXRequestMixin, ListView):
    template_name = "wizard/wizard_sections.html"
    context_object_name = "wizard_sections"
    model = WizardSection

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['step'] = int(self.request.GET.get("step"))
        return context


class WizardFormView(AJAXRequestMixin, FormView):
    form_class = ProjectForm
    template_name = "wizard/form.html"
    step = 1

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['step'] = self.step
        context['total_steps'] = WizardSection.objects.count()
        return context

    def get_success_url(self):
        return reverse(f"wizard:setup_step_{self.step + 1}")

    def update_status(self):
        current_section = WizardSection.objects.all()[self.step - 1]
        WizardSection.objects.filter(id=current_section.id).update(status=COMPLETED_CHOICE)
        WizardSection.objects.filter(id=current_section.id + 1, status=NOT_STARTED_CHOICE).update(
            status=IN_PROGRESS_CHOICE
        )


class ProjectUpdateView(WizardFormView, UpdateView):

    def get_object(self, queryset=None):
        obj = Project.objects.first()
        if not obj:
            obj = Project()
        return obj

    def form_valid(self, form):
        self.object = form.save()
        self.update_status()
        return super().form_valid(form)


class AdministrativeLevelsFormView(WizardFormView):
    form_class = AdministrativeLevelFormSet
    template_name = "wizard/formset.html"
    step = 2

    def get_form(self, form_class=None):
        queryset = AdministrativeLevel.objects.annotate(
            has_issue=Exists(Issue.objects.filter(administrative_region__administrative_level=OuterRef("pk"))),
            has_issue_department=Exists(
                IssueDepartmentAdministrativeLevel.objects.filter(administrative_level=OuterRef("pk"))
            ),
        ).annotate(
            restricted_deletion=(
                Exists(Issue.objects.filter(administrative_region__administrative_level=OuterRef("pk")))
                | Exists(IssueDepartmentAdministrativeLevel.objects.filter(administrative_level=OuterRef("pk")))
            )
        )
        return AdministrativeLevelFormSet(queryset=queryset, **self.get_form_kwargs())

    def form_valid(self, form):
        form.save()
        self.update_status()
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['formset'] = context['form']  # Aliases for clarity in the template
        context['formset_label'] = _('Administrative Levels')
        return context


class RolesAndResponsibilitiesFormView(WizardFormView):
    template_name = "wizard/example.html"
    step = 3
