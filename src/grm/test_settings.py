# ruff: noqa: F405
import logging

try:
    from grm.settings import *  # noqa
except ImportError:
    pass

MIDDLEWARE = [
    middleware
    for middleware in MIDDLEWARE
    if middleware
    not in [  # noqa: F405
        "django.middleware.security.SecurityMiddleware",
        "corsheaders.middleware.CorsMiddleware",
        "django.middleware.common.CommonMiddleware",
        "django.middleware.csrf.CsrfViewMiddleware",
        "django.middleware.clickjacking.XFrameOptionsMiddleware",
    ]
]

INSTALLED_APPS = [app for app in INSTALLED_APPS if app not in ["django.contrib.staticfiles"]]  # noqa: F405

PASSWORD_HASHERS = ("django.contrib.auth.hashers.MD5PasswordHasher",)

MEDIA_URL = "/media/"

logging.disable(logging.CRITICAL)

COUCHDB_DATABASE = COUCHDB_GRM_DATABASE = COUCHDB_ATTACHMENT_DATABASE = COUCHDB_GRM_ATTACHMENT_DATABASE = "test"

LANGUAGE_CODE = "en-us"

# Prevents the creation of huggingface.log during testing
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'common.utils.huggingface_connector': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
