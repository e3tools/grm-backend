# uncomment to use
# useful to debug requests
LOCAL_INSTALLED_APPS = [
    # "debug_toolbar",
    # "query_inspector",
    # "django_extensions",
]

LOCAL_MIDDLEWARE = [
    # "debug_toolbar.middleware.DebugToolbarMiddleware",
    # "query_inspector.middleware.QueryCountMiddleware",
]

INTERNAL_IPS = [
    "127.0.0.1",
    "localhost",
]

ALLOWED_HOSTS = ["*"]
CSRF_TRUSTED_ORIGINS = ["https://*.mgp.coso.gouv.bj", "https://*.127.0.0.1"]

# Language to execute Django commands that use the TranslatedBaseCommand (optional)
CMD_LANGUAGE_CODE = 'en-us'

# Instead of sending out real SMS the console backend just writes the SMS that would be sent to the standard output.
TWILIO_DEBUG_MODE = True
