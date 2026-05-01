"""
Django settings TESTING (UTA) — PracticaYoruba API.

BD separada de produccion: practicayoruba_uta
pytest apunta a este settings via pytest.ini
"""
from .base import *

DEBUG = False

# BD exclusiva para tests — nunca toca practicayoruba_db
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_UTA_NAME', default='practicayoruba_uta'),
        'USER': config('DB_UTA_USER', default='django_user'),
        'PASSWORD': config('DB_UTA_PASSWORD', default='django_pass'),
        'HOST': config('DB_UTA_HOST', default='127.0.0.1'),
        'PORT': config('DB_UTA_PORT', default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'TEST': {
            'NAME': config('DB_UTA_NAME', default='practicayoruba_uta'),
            'CHARSET': 'utf8mb4',
            'COLLATION': 'utf8mb4_unicode_ci',
        },
    }
}

# Hasher mas rapido en tests — no MD5, usamos PBKDF2 con menos iteraciones
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

# Sin throttling en tests
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []

# Sin logs en consola durante tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {
        'null': {'class': 'logging.NullHandler'},
    },
    'root': {
        'handlers': ['null'],
    },
}
