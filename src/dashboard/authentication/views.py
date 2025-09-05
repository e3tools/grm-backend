from django.contrib.auth.views import LoginView
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from rest_framework import status

from dashboard.authentication.forms import EmailAuthenticationForm
from dashboard.grm.constants import COMPLETE_CHOICE
from wizard.models import WizardSession


def handler400(request, exception):
    return render(
        request,
        template_name="common/400.html",
        status=status.HTTP_400_BAD_REQUEST,
        content_type="text/html",
    )


def handler403(request, exception):
    return render(
        request,
        template_name="common/403.html",
        status=status.HTTP_403_FORBIDDEN,
        content_type="text/html",
    )


def handler404(request, exception):
    return render(
        request,
        template_name="common/404.html",
        status=status.HTTP_404_NOT_FOUND,
        content_type="text/html",
    )


def handler500(request):
    return render(
        request,
        template_name="common/500.html",
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content_type="text/html",
    )


class CustomLoginView(LoginView):
    """
    Custom login view that blocks non-GRM managers when the wizard is incomplete.
    """

    authentication_form = EmailAuthenticationForm
    template_name = "authentication/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        user = form.get_user()

        # Wizard check
        session = WizardSession.get_wizard_session()
        if not user.grm_manager and session.state != COMPLETE_CHOICE:
            form.add_error(None, _("Login is not allowed until the customization wizard is completed."))
            return self.form_invalid(form)

        return super().form_valid(form)
