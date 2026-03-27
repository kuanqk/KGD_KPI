from .base import *
from decouple import config

DEBUG = True

ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'NAME': config('DB_NAME', default='kgd_kpi'),
        'USER': config('DB_USER', default='kgd_user'),
        'PASSWORD': config('DB_PASSWORD', default=''),
    }
}

# Allow all CORS in dev
CORS_ALLOW_ALL_ORIGINS = True

# Django debug toolbar (optional, install separately)
# INSTALLED_APPS += ['debug_toolbar']
