from django.http import Http404
from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.utils.deprecation import MiddlewareMixin

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
        if "dashboard" not in resolver.namespaces and "wizard" not in resolver.namespace:
            return self.get_response(request)

        # Allow static and media
        if request.path.startswith("/static/") or request.path.startswith("/media/"):
            return self.get_response(request)

        # Wizard complete
        if WizardSection.wizard_setup_is_completed():
            if request.path == self.customization_url:
                raise Http404()
        else:
            # Wizard incomplete
            if request.user.is_authenticated and request.user.grm_manager:
                if request.path != self.logout_url and "wizard" not in resolver.namespaces:
                    return redirect(self.customization_url)
            else:
                if request.path not in self.exempt_urls_incomplete_non_manager:
                    raise Http404()

        return self.get_response(request)


class DisableWizardCacheMiddleware(MiddlewareMixin):
    """
    Middleware that disables browser caching for all wizard URLs.
    This ensures that when the user presses the Back button,
    the browser must re-fetch the page, allowing other middleware
    (like WizardRedirectMiddleware) to enforce logic.
    """

    def process_response(self, request, response):
        resolver = resolve(request.path_info)
        if "wizard" in resolver.namespace:
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"
        return response
