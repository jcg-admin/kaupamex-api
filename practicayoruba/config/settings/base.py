from pathlib import Path
from datetime import timedelta
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-CHANGE-ME')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'drf_spectacular',
    'apps.core',
    'apps.users',
    'apps.settings_app',
    'apps.catalogue',
    'apps.chartsize',
    'apps.inventory',
    'apps.cart',
    'apps.voucher',
    'apps.wishlist',
    'apps.orders',
    'apps.payments',
    'apps.support',
    'apps.returns',
    'apps.notifications',
    'apps.contact',
    'apps.newsletter',
    'apps.questions',
    'apps.reports',
    'apps.logistics',
    'apps.reviews',
    'apps.search_history',
    'apps.static_content',
]

AUTH_USER_MODEL = 'users.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
    ]},
}]

WSGI_APPLICATION = 'config.wsgi.application'

# Conexion DB — socket Unix preferido (convencion del proyecto:
# "se tienen que conectar x socket"). Si DB_SOCKET esta seteada,
# Django/mysqlclient ignora HOST/PORT y usa el socket directamente.
# Fallback TCP cuando DB_SOCKET no esta seteada (CI runners
# remotos, conexion cross-host). Ver
# docs/source/normativa/procedimientos/proc-ejecutar-pruebas.rst.
_DB_OPTIONS = {
    'charset': 'utf8mb4',
    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
}
_DB_SOCKET = config('DB_SOCKET', default='')
if _DB_SOCKET:
    _DB_OPTIONS['unix_socket'] = _DB_SOCKET

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': config('DB_NAME', default='practicayoruba_db'),
        'USER': config('DB_USER', default='django_user'),
        'PASSWORD': config('DB_PASSWORD', default='django_pass'),
        'HOST': config('DB_HOST', default='127.0.0.1'),
        'PORT': config('DB_PORT', default='3306'),
        'OPTIONS': _DB_OPTIONS,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Dirección remitente por defecto para todos los emails del sistema.
# Sobrescribir en production.py via decouple si se necesita otro valor.
DEFAULT_FROM_EMAIL = 'noreply@practicayoruba.mx'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # DEC-THR-1 (hardening-throttle-endpoints-publicos):
    # Defense in depth contra brute-force/spam en endpoints
    # publicos. Rates conservadores por scope sensible.
    # testing.py desactiva DEFAULT_THROTTLE_CLASSES para tests.
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon':                '100/hour',
        'user':                '1000/hour',
        'register':            '5/hour',
        'password_reset':      '5/hour',
        'password_confirm':    '10/hour',
        'email_verify':        '10/hour',
        'resend_verification': '3/hour',
        'contact':             '5/hour',
        'addresses':           '30/hour',
        'change_password':     '5/hour',   # D-04-08
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

SPECTACULAR_SETTINGS = {
    # --- Metadatos ---
    'TITLE': 'PracticaYoruba API',
    'DESCRIPTION': (
        'API REST de PracticaYoruba — plataforma e-commerce de productos Yoruba.\n\n'
        'Autenticación: JWT Bearer token via POST /api/v1/auth/login/\n'
        'Todos los endpoints bajo el prefijo /api/v1/'
    ),
    'VERSION': '1.0.0',
    'CONTACT': {
        'name': 'Equipo PracticaYoruba',
        'email': 'dev@practicayoruba.mx',
    },
    'LICENSE': {'name': 'Propietario'},

    # --- Schema ---
    'SERVE_INCLUDE_SCHEMA': False,   # el endpoint /api/schema/ no aparece en el schema
    'SERVE_PUBLIC': True,
    'SERVE_PERMISSIONS': ['rest_framework.permissions.AllowAny'],
    # Strips /api/v1 del path al generar los tags automaticamente:
    # /api/v1/auth/login/ → tag "auth"
    # /api/v1/config/settings/ → tag "config"
    'SCHEMA_PATH_PREFIX': r'/api/v[0-9]+',

    # --- Componentes ---
    # Genera componentes separados para request y response cuando difieren
    'COMPONENT_SPLIT_REQUEST': True,
    # PATCH genera un schema donde ningun campo es required
    'COMPONENT_SPLIT_PATCH': True,

    # --- OpenAPI version ---
    'OAS_VERSION': '3.0.3',

    # --- Swagger UI ---
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,   # el JWT persiste al recargar la UI
        'displayOperationId': False,
        'filter': True,
        'docExpansion': 'none',
        'defaultModelsExpandDepth': 2,
    },

    # --- Redoc ---
    'REDOC_UI_SETTINGS': {
        'hideDownloadButton': False,
        'expandResponses': '200,201',
        'requiredPropsFirst': True,
    },

    # --- Ordenamiento y hooks ---
    'SORT_OPERATIONS': True,
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.hooks.postprocess_schema_enums',
        # OCP: agrega SPECTACULAR_TAGS de cada apps/*/schema.py sin tocar base.py
        'config.spectacular_hooks.collect_app_tags',
    ],
    'PREPROCESSING_HOOKS': [
        # Elimina endpoints duplicados con sufijo {format} (ej: /products.json)
        'drf_spectacular.hooks.preprocess_exclude_path_format',
    ],

    # --- Enums ---
    'ENUM_GENERATE_CHOICE_DESCRIPTION': True,
    'ENUM_SUFFIX': '',

    # D-032 T-4: cada modelo con campos 'status' o 'gateway' tiene su
    # propio choice set. Sin overrides drf-spectacular auto-resuelve
    # con sufijos hex (StatusFc3Enum, Gateway409Enum) — feo en clientes
    # generados. Cada entrada mapea EnumName -> path al choice set.
    'ENUM_NAME_OVERRIDES': {
        # status fields (mas de un modelo usa este nombre de campo)
        'OrderStatusEnum':
            'apps.orders.models.Order.STATUSES',
        'PaymentStatusEnum':
            'apps.payments.models.Payment.STATUSES',
        'RefundStatusEnum':
            'apps.payments.models.Refund.STATUSES',
        'ReviewStatusEnum':
            'apps.reviews.models.Review.STATUSES',
        'ShipmentGuideStatusEnum':
            'apps.logistics.models.ShipmentGuide.STATUSES',
        'StaticPageVersionStatusEnum':
            'apps.settings_app.models.StaticPageVersion.STATUS_CHOICES',
        'NotificationStatusEnum':
            'apps.notifications.models.ManualNotification.Status.choices',
        'NewsletterSubscriberStatusEnum':
            'apps.newsletter.models.SubscriberStatus.choices',
        'QuestionStatusEnum':
            'apps.questions.models.QuestionStatus.choices',
        'SupportTicketStatusEnum':
            'apps.support.models.SupportTicket.Status.choices',
        'ReturnRequestStatusEnum':
            'apps.returns.models.ReturnRequest.Status.choices',
        # gateway fields (Payment vs PaymentGateway tienen choice sets
        # diferentes — el segundo agrega TEST sandbox)
        'PaymentGatewayChoiceEnum':
            'apps.payments.models.Payment.GATEWAYS',
        'PaymentGatewayConfigEnum':
            'apps.settings_app.models.PaymentGateway.GATEWAYS',
        # AudienceFilterEnum: alias para ManualNotification.RecipientType
        # que aparece en serializers diferentes con choice set identico
        'AudienceFilterEnum':
            'apps.notifications.models.ManualNotification.RecipientType.choices',
    },
}

# H-09: ensure logs directory exists on fresh checkouts before RotatingFileHandler
# tries to open the file. Using mkdir(parents=True, exist_ok=True) is idempotent
# and keeps the existing deployment assumption (logs live under BASE_DIR/logs).
LOG_DIR = BASE_DIR / 'logs'
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': LOG_DIR / 'django.log',
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 3,
        },
    },
    'loggers': {
        'django': {'handlers': ['console', 'file'], 'level': 'INFO'},
        'apps':   {'handlers': ['console', 'file'], 'level': 'INFO'},
    },
}

SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Cache — DatabaseCache (cnst-arquitectura T4/T5).
# UC-SRCH-02 (autocomplete) usa la clave "autocomplete:<prefijo>" con TTL 60s.
# UC-CAT-08 (árbol de categorías) usará la clave "categories:tree" con TTL 300s.
# La tabla se crea con: python manage.py createcachetable
# En testing.py se sobrescribe con LocMemCache para evitar dependencia de BD.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'cache_table',
        'TIMEOUT': 300,
        'OPTIONS': {
            'MAX_ENTRIES': 5000,
            'CULL_FREQUENCY': 4,
        },
    }
}
