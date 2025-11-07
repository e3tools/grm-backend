from django.contrib.auth.views import LoginView
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from rest_framework import status

from dashboard.authentication.forms import EmailAuthenticationForm
from wizard.models import WizardSection


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
    Custom login view with access control.

    Blocks:
    - Facilitators: Not authorized to access the dashboard
    - Non-GRM owners: When the wizard is incomplete
    """

    authentication_form = EmailAuthenticationForm
    template_name = "authentication/login.html"
    redirect_authenticated_user = True
    extra_context = {'title': _("Log in")}

    def form_valid(self, form):
        user = form.get_user()

        # Block Facilitators from accessing the dashboard
        if hasattr(user, 'facilitator'):
            form.add_error(
                None,
                _(
                    "Your user account is not authorized to access this system. "
                    "Please use the mobile application instead."
                ),
            )
            return self.form_invalid(form)

        # Wizard check
        wizard_setup_is_completed = WizardSection.wizard_setup_is_completed()
        if not user.grm_owner and not wizard_setup_is_completed:
            form.add_error(None, _("Login is not allowed until the customization wizard is completed."))
            return self.form_invalid(form)

        return super().form_valid(form)
