import logging

try:
    from grm.settings import *
except ImportError:
    pass

MIDDLEWARE = [
    middleware for middleware in MIDDLEWARE if middleware not in [
        'django.middleware.security.SecurityMiddleware',
        'corsheaders.middleware.CorsMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware'
    ]
]

INSTALLED_APPS = [
    app for app in INSTALLED_APPS if app not in [
        'django.contrib.staticfiles'
    ]
]

PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.MD5PasswordHasher',
)

MEDIA_URL = '/media/'

logging.disable(logging.CRITICAL)

COUCHDB_DATABASE = COUCHDB_GRM_DATABASE = COUCHDB_ATTACHMENT_DATABASE = COUCHDB_GRM_ATTACHMENT_DATABASE = 'test'
