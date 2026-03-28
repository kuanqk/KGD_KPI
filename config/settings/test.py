"""Настройки для локального запуска тестов без PostgreSQL (SQLite)."""
from .base import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db_test.sqlite3',
    }
}

# Ускоряем хэширование паролей в тестах
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
