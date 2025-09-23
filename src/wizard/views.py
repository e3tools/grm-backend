from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import FormView, ListView, TemplateView, UpdateView

from dashboard.mixins import AJAXRequestMixin
from dashboard.models import Project
from grm.constants import COMPLETED_CHOICE, IN_PROGRESS_CHOICE
from wizard.forms import ProjectForm
from wizard.models import WizardSection


class CustomizationWizardView(LoginRequiredMixin, TemplateView):
    template_name = "wizard/grm_customization.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_steps'] = WizardSection.objects.count()
        return context


class WizardSectionListView(AJAXRequestMixin, ListView):
    template_name = "wizard/wizard_sections.html"
    context_object_name = "wizard_sections"
    model = WizardSection


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
        WizardSection.objects.filter(id=current_section.id + 1).update(status=IN_PROGRESS_CHOICE)


class ProjectUpdateView(WizardFormView, UpdateView):

    def get_object(self, queryset=None):
        obj = Project.objects.first()
        if not obj:
            obj = Project()
        return obj

    def form_valid(self, form):
        """If the form is valid, save the associated model."""
        self.object = form.save()
        self.update_status()
        return super().form_valid(form)


class AdministrativeLevelsFormView(WizardFormView):
    template_name = "wizard/example_step_2.html"
    step = 2
