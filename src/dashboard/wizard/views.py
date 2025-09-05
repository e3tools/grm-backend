from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class CustomizationWizardView(LoginRequiredMixin, TemplateView):
    template_name = "wizard/chatbot.html"
