from django.shortcuts import redirect
from django.urls import resolve, reverse

from dashboard.grm.constants import COMPLETE_CHOICE
from wizard.models import WizardSession


class WizardRedirectMiddleware:
    """
    Middleware that enforces wizard completion only for URLs under the "dashboard" namespace.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_urls = {
            reverse("dashboard:wizard:customization_wizard"),
            reverse("dashboard:authentication:logout"),
        }

    def __call__(self, request):
        resolver = resolve(request.path_info)

        # Enforce wizard only for dashboard namespace
        if "dashboard" not in resolver.namespaces:
            return self.get_response(request)

        # Allow static files and media
        if request.path.startswith("/static/") or request.path.startswith("/media/"):
            return self.get_response(request)

        # Check wizard state for authenticated users
        if request.user.is_authenticated:
            session = WizardSession.get_wizard_session()
            if not session or session.state != COMPLETE_CHOICE:
                # Block non-GRM managers from dashboard
                if request.user.grm_manager:
                    if request.path not in self.exempt_urls:
                        return redirect("dashboard:wizard:customization_wizard")
                else:
                    if request.path != reverse("dashboard:authentication:logout"):
                        return redirect("admin:login")

        # Skip exempt URLs
        if request.path in self.exempt_urls | {reverse("dashboard:authentication:login")}:
            return self.get_response(request)

        return self.get_response(request)
