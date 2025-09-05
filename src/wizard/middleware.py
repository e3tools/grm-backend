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
            reverse("dashboard:authentication:login"),
            reverse("dashboard:wizard:customization_wizard"),
            reverse("dashboard:authentication:logout"),
        }

    def __call__(self, request):
        resolver = resolve(request.path_info)

        # Allow static files and media
        if request.path.startswith("/static/") or request.path.startswith("/media/"):
            return self.get_response(request)

        # Skip exempt URLs
        if request.path in self.exempt_urls:
            return self.get_response(request)

        # Enforce wizard only for dashboard namespace
        if "dashboard" not in resolver.namespaces:
            return self.get_response(request)

        # Check wizard state
        session = WizardSession.get_wizard_session()
        if not session or session.state != COMPLETE_CHOICE:
            return redirect("dashboard:wizard:customization_wizard")

        return self.get_response(request)
