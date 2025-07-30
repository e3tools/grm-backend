from django.middleware.locale import LocaleMiddleware
from django.utils import translation
from django.conf import settings


class CustomLocaleMiddleware(LocaleMiddleware):
    """
    Custom locale middleware that ignores browser language preferences for first-time visitors.

    This middleware extends Django's LocaleMiddleware to provide a more controlled
    language selection behavior. Instead of automatically using the browser's
    Accept-Language header for new visitors, it defaults to the site's LANGUAGE_CODE
    setting until the user explicitly chooses a different language.

    Behavior:
    - First-time visitors: Always see the default language (LANGUAGE_CODE)
    - Returning visitors: See their previously chosen language (from cookie or session)
    - Ignores browser Accept-Language headers for new visitors

    Usage:
        Add this middleware to your MIDDLEWARE setting in place of Django's
        'django.middleware.locale.LocaleMiddleware':

        MIDDLEWARE = [
            # ... other middlewares
            'grm.middleware.locale.CustomLocaleMiddleware',
            # ... other middlewares
        ]
    """

    def process_request(self, request):
        """
        Process the incoming request to determine the appropriate language.

        This method checks if the user has previously selected a language
        (stored in cookies or session). If no previous language selection
        is found, it defaults to the site's LANGUAGE_CODE setting instead
        of checking browser preferences.

        Args:
            request: The incoming HTTP request object

        Returns:
            None: The method modifies the request object in place
        """
        # Check if user has previously chosen a language via cookie
        language_from_cookie = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)

        # Check if user has previously chosen a language via session
        # Django stores language preference in session with this key
        language_from_session = request.session.get('_language')

        # If no language is stored (first-time visitor), use default language
        if not language_from_cookie and not language_from_session:
            # Activate the default language (French in this case)
            translation.activate(settings.LANGUAGE_CODE)
            request.LANGUAGE_CODE = settings.LANGUAGE_CODE
            return

        # If user has previously chosen a language, use Django's default behavior
        # This will respect the stored language preference
        super().process_request(request)