from django.http import Http404
from django.shortcuts import redirect
from django.urls import resolve, reverse

from grm.constants import COMPLETED_CHOICE
from wizard.models import WizardSection


class WizardRedirectMiddleware:
    """
    Middleware that enforces wizard completion only for URLs under the "dashboard" namespace.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.customization_url = reverse("wizard:customization_wizard")
        self.login_url = reverse("dashboard:authentication:login")
        self.logout_url = reverse("dashboard:authentication:logout")

        self.exempt_urls_incomplete_manager = {self.logout_url, self.customization_url}
        self.exempt_urls_incomplete_non_manager = {self.login_url, self.logout_url}

    def __call__(self, request):
        resolver = resolve(request.path_info)

        # Enforce only under dashboard
        if "dashboard" not in resolver.namespaces and request.path != self.customization_url:
            return self.get_response(request)

        # Allow static and media
        if request.path.startswith("/static/") or request.path.startswith("/media/"):
            return self.get_response(request)

        wizard_setup_status = WizardSection.get_wizard_setup_status()

        # Wizard incomplete
        if wizard_setup_status != COMPLETED_CHOICE:
            if request.user.is_authenticated and request.user.grm_manager:
                if request.path not in self.exempt_urls_incomplete_manager:
                    return redirect(self.customization_url)
            else:
                if request.path not in self.exempt_urls_incomplete_non_manager:
                    raise Http404()
            return self.get_response(request)

        # Wizard complete
        if request.user.is_authenticated and not request.user.grm_manager:
            if request.path == self.customization_url:
                raise Http404()

        return self.get_response(request)
