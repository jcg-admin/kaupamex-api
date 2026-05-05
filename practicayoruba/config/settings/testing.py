"""
Django settings TESTING (QA) — PracticaYoruba API.

BD exclusiva para tests: practicayoruba_qa (MySQL/MariaDB).
Separada de produccion. pytest apunta aqui via pytest.ini.

Arranque de MariaDB en entornos sin systemd:
  nohup su -s /bin/bash mysql -c "/usr/sbin/mariadbd \\
    --datadir=/var/lib/mysql --socket=/run/mysqld/mysqld.sock \\
    --pid-file=/run/mysqld/mysqld.pid --bind-address=127.0.0.1 \\
    --port=3306" &> /tmp/mariadbd.log &
"""
from .base import *

DEBUG = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME':     config('DB_QA_NAME',     default='practicayoruba_qa'),
        'USER':     config('DB_QA_USER',     default='django_user'),
        'PASSWORD': config('DB_QA_PASSWORD', default='django_pass'),
        'HOST':     config('DB_QA_HOST',     default='127.0.0.1'),
        'PORT':     config('DB_QA_PORT',     default='3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
        'TEST': {
            'NAME':      config('DB_QA_NAME', default='practicayoruba_qa'),
            'CHARSET':   'utf8mb4',
            'COLLATION': 'utf8mb4_unicode_ci',
        },
    }
}


# drf-spectacular — en tests no se necesitan las UIs, solo el schema endpoint
SPECTACULAR_SETTINGS = {
    **SPECTACULAR_SETTINGS,
    'SERVE_PUBLIC': True,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
}

# Hasher mas rapido en tests
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

# Sin throttling en tests
REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []

# Sin logs en consola durante tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'root':     {'handlers': ['null']},
}
