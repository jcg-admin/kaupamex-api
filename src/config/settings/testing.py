"""
Django settings TESTING (QA) — Kaupamex API.

BD exclusiva para tests: ``kaupamex_core_qa`` (SOL-087), definido en ``src/.env``
(sin ``default=`` en el código — todo vive en el env). Separada de produccion.
pytest apunta aqui via pytest.ini.

Arranque de PostgreSQL en entornos sin systemd: NO se replica el
``nohup mariadbd`` de la era MariaDB. En Debian/Ubuntu el motor se opera por
**cluster**, y arrancarlo a mano lo deja fuera del registro de
``postgresql-common`` (``pg_lsclusters`` deja de decir la verdad)::

    pg_ctlcluster 16 main start      # arrancar
    pg_lsclusters                    # ver estado
    pg_isready                       # probe de disponibilidad

Ver el skill ``db: .claude/skills/db-postgres/SKILL.md`` §1.
"""
import certifi
import tempfile
from .base import *
from config.settings.options import get as opt

DEBUG = False

# MEDIA_ROOT aislado a un tmpdir: los tests que suben/guardan archivos
# (inventory import, reviews images, catalogue import) NO deben escribir al
# media/ del repo — no es hermetico y depende de permisos del FS (el usuario
# 'develop' no puede escribir el media/ del repo). (H-API-02)
MEDIA_ROOT = tempfile.mkdtemp(prefix='pyqa-media-')

# Vacio a proposito: ``charset`` e ``init_command`` no tienen equivalente en
# PostgreSQL — ver la explicacion en ``base.py``, no se repite aqui.
_DB_QA_OPTIONS = {}
# SSL: por defecto se verifica el cert del server contra CAs publicas
# (certifi), valido para la DB productiva (Let's Encrypt). En CI la DB es un
# service container SIN SSL compilado; DB_QA_SSL_MODE=disable apaga TLS para
# ese entorno sin afectar local (socket) ni produccion (TCP+SSL).
# El literal es ``disable`` — uno de los seis que libpq acepta (disable, allow,
# prefer, require, verify-ca, verify-full). ``DISABLED`` NO existe: baja a
# ``disabled`` por el ``.lower()`` y libpq lo rechaza al conectar con
# ``invalid sslmode value: "disabled"``. Ver H-API-574.
# DB_QA_SSL_MODE y DB_QA_SOCKET son TOGGLES OPCIONALES (paridad con base.py):
# su ausencia tiene un significado definido por el guard ``if _X:`` de abajo
# (verificar cert contra CAs publicas / fallback TCP). Llevan ``default=''`` a
# proposito — las claves de CONEXION QA (DB_QA_NAME/USER/PASSWORD/HOST/PORT) si
# son sin ``default=`` por SOL-087. Sin el default, el import crasheaba en CI
# (no hay ``.env``; el workflow no exporta DB_QA_SOCKET, cuya ausencia es
# justamente el fallback TCP esperado).
_DB_QA_SSL_MODE = opt('DB_QA_SSL_MODE')
if _DB_QA_SSL_MODE:
    _DB_QA_OPTIONS['sslmode'] = _DB_QA_SSL_MODE.lower()
else:
    _DB_QA_OPTIONS['sslmode'] = 'verify-full'
    _DB_QA_OPTIONS['sslrootcert'] = certifi.where()
# El socket es el HOST en libpq, no una opcion — ver ``base.py`` y H-API-305.
_DB_QA_SOCKET = opt('DB_QA_SOCKET')

# Config de conexión QA — SIN ``default=`` (SOL-087): todo vive en ``.env``.
# El schema de tests es ``kaupamex_core_qa`` (DB_QA_NAME en ``src/.env``).
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME':     opt('DB_QA_NAME'),
        'USER':     opt('DB_QA_USER'),
        'PASSWORD': opt('DB_QA_PASSWORD'),
        'HOST':     _DB_QA_SOCKET or opt('DB_QA_HOST'),
        'PORT':     opt('DB_QA_PORT'),
        'OPTIONS': _DB_QA_OPTIONS,
        # ``CHARSET``/``COLLATION`` se retiran: en PostgreSQL el encoding y la
        # collation son de la DATABASE, fijados al crearla. Django los ignora
        # para este backend, asi que dejarlos seria decoracion que miente.
        'TEST': {
            'NAME': opt('DB_QA_NAME'),
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

# Sin logs en consola durante tests — pero el árbol queda VIVO (H-API-749).
#
# ``disable_existing_loggers: True`` no silencia: **apaga**. Un logger con
# ``disabled = True`` descarta el registro dentro de ``Logger.handle()``, antes
# de todo handler y antes de propagar, así que ``caplog`` no ve nada y su
# silencio se lee como «no se emitió» — una aserción negativa pasa por vacuidad.
# Medido con `disable_existing_loggers: True`: 15 loggers apagados —los de
# Django (``django``, ``django.request``, ``django.db.backends``…), ``psycopg``,
# ``asyncio`` y ``service.db``—, que son los que ya existían cuando corre
# ``dictConfig``. Los 76 de ``addons.*`` nacen después y quedan vivos: la
# ceguera era asimétrica y por eso costaba verla.
#
# Con ``False`` el árbol emite y nadie lo oye: el único handler es el
# ``NullHandler`` de la raíz. El nivel efectivo de ``django`` es INFO, así que
# ``django.db.backends`` (que registra el SQL en DEBUG) sigue callado.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'root':     {'handlers': ['null']},
}

# Email — locmem para tests (django.core.mail.outbox)
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
FRONTEND_URL = "http://localhost:3001"
# dispatch_email usa ThreadPoolExecutor; en tests debe ser sincrono para
# que mail.outbox este poblado cuando el test asserta (race condition).
DISPATCH_EMAIL_SYNC = True

# Conexion no persistente en tests: cada test cierra la suya. Evita que una
# transaccion abierta de un test bloquee al siguiente. El comentario decia
# "MySQL en testing" — drift de ADR-028, que movio el motor a PostgreSQL el
# 2026-08-06; se corrige aqui por ser el pase que toca el archivo.
DATABASES['default']['CONN_MAX_AGE'] = 0
DATABASES['default']['OPTIONS']['connect_timeout'] = 10

# Cache — LocMemCache en tests
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache',
    }
}
