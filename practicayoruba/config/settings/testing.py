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

# MEDIA_ROOT aislado a un tmpdir: los tests que suben/guardan archivos
# (inventory import, reviews images, catalogue import) NO deben escribir al
# media/ del repo — no es hermetico y depende de permisos del FS (el usuario
# 'develop' no puede escribir el media/ del repo). (H-API-02)
import tempfile
MEDIA_ROOT = tempfile.mkdtemp(prefix='pyqa-media-')

_DB_QA_OPTIONS = {
    'charset': 'utf8mb4',
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
}
_DB_QA_SOCKET = config('DB_QA_SOCKET', default='')
if _DB_QA_SOCKET:
    _DB_QA_OPTIONS['unix_socket'] = _DB_QA_SOCKET

_DB_QA_SSL_MODE = config('DB_QA_SSL_MODE', default='')
_DB_QA_SSL_CA   = config('DB_QA_SSL_CA',   default='')
if _DB_QA_SSL_MODE or _DB_QA_SSL_CA:
    _qa_ssl_opts = {}
    if _DB_QA_SSL_CA:
        _qa_ssl_opts['ca'] = _DB_QA_SSL_CA
    _DB_QA_OPTIONS['ssl'] = _qa_ssl_opts
    if _DB_QA_SSL_MODE:
        _DB_QA_OPTIONS['ssl_mode'] = _DB_QA_SSL_MODE

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME':     config('DB_QA_NAME',     default='practicayoruba_qa'),
        'USER':     config('DB_QA_USER',     default='django_user'),
        'PASSWORD': config('DB_QA_PASSWORD', default='django_pass'),
        'HOST':     config('DB_QA_HOST',     default='127.0.0.1'),
        'PORT':     config('DB_QA_PORT',     default='3306'),
        'OPTIONS': _DB_QA_OPTIONS,
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

# JWT — clave de firma exclusiva para tests
SIMPLE_JWT = {
    **SIMPLE_JWT,
    'SIGNING_KEY': 'testing-signing-key-please-do-not-use-in-production-0123456789',
}

# ALLOWED_HOSTS para pruebas
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']

# Sin logs en consola durante tests
LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'root':     {'handlers': ['null']},
}

# Email — locmem para tests (django.core.mail.outbox)
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
FRONTEND_URL = "http://localhost:3001"
# dispatch_email usa ThreadPoolExecutor; en tests debe ser sincrono para
# que mail.outbox este poblado cuando el test asserta (race condition).
DISPATCH_EMAIL_SYNC = True

# MySQL en testing — evitar deadlocks por conexiones persistentes
DATABASES['default']['CONN_MAX_AGE'] = 0
DATABASES['default']['OPTIONS']['connect_timeout'] = 10

# Cache — LocMemCache en tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}
