from pathlib import Path
from datetime import timedelta
from decouple import config, Csv
import certifi

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
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
    'apps.backups',
    'apps.referral',
]

AUTH_USER_MODEL = 'users.User'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # CookieGovernanceMiddleware va sobre Session/CSRF: su process_response
    # (orden inverso) corre despues de que aquellas ponen sus cookies, para
    # observarlas/gobernarlas. Fase 1 = auditoria (COOKIE_GOVERNANCE_ENFORCE
    # por defecto False). Ver iniciativa migrar-auth-sesion-cookie-httponly.
    'apps.core.middleware.cookie_governance.CookieGovernanceMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # H-CART-01 Fase 2: fija la cookie httpOnly cart_token para carritos
    # anonimos. Va por DEBAJO de CookieGovernanceMiddleware para que el
    # process_response de aquel (orden inverso) observe la cookie de carrito.
    'apps.cart.middleware.CartCookieMiddleware',
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

# Conexion DB — socket Unix preferido en dev local (si DB_SOCKET está
# seteada, mysqlclient ignora HOST/PORT). En produccion OVH (VM1→VM3)
# se usa TCP con SSL obligatorio (require_secure_transport=ON en VM3).
# Ver docs/source/normativa/procedimientos/proc-ejecutar-pruebas.rst.
_DB_OPTIONS = {
    'ssl': {
        'ca': certifi.where(),  # Bundle CAs publico — valido para Let's Encrypt
    },
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
        'USER': config('DB_USER', default='practicayoruba_app'),
        'PASSWORD': config('DB_PASSWORD', default=''),
        'HOST': config('DB_HOST', default='db.practicayoruba.com'),
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
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Dirección remitente por defecto para todos los emails del sistema.
# Sobrescribir en production.py via decouple si se necesita otro valor.
DEFAULT_FROM_EMAIL = 'noreply@practicayoruba.com'

# Destinatario de alertas operativas (UC-ADM-05: backup fallido). El backup
# on-demand notifica a esta dirección cuando backup_db.sh termina en error.
BACKUP_ALERT_EMAIL = config('BACKUP_ALERT_EMAIL', default='admin@practicayoruba.com')

# Buzones por propósito en VM2 (Postfix + Cyrus). Los emails transaccionales
# (auth, órdenes, devoluciones, soporte) salen de DEFAULT_FROM_EMAIL (noreply@).
# Contacto y newsletter usan su buzón monitoreado para que la conversación
# llegue a un humano y las respuestas no caigan en un buzón no-reply.
CONTACT_FROM_EMAIL = config('CONTACT_FROM_EMAIL', default='hola@practicayoruba.com')
CONTACT_NOTIFY_EMAIL = config('CONTACT_NOTIFY_EMAIL', default='hola@practicayoruba.com')
NEWSLETTER_FROM_EMAIL = config('NEWSLETTER_FROM_EMAIL', default='newsletter@practicayoruba.com')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        # ADR-018 — migracion completa a sesion de servidor (web).
        # La UNICA auth por defecto es la cookie de sesion HttpOnly, exenta
        # de token CSRF: la defensa CSRF es SameSite=Strict + prefijo __Host-
        # (la cookie no viaja cross-site, que es el vector de CSRF). Esto
        # arregla el incidente en que las mutaciones por sesion pedian
        # X-CSRFToken y el SPA, tras recargar (JWT en memoria perdido), no lo
        # tenia -> 403 -> logout. Ver analisis-incidente-csrf-mutaciones.
        #
        # JWT (SimpleJWT) queda INSTALADO pero fuera del default: el login aun
        # emite tokens (dormidos). Para una futura app movil basta re-anadir
        # 'rest_framework_simplejwt.authentication.JWTAuthentication' aqui.
        'apps.users.authentication.CsrfExemptSessionAuthentication',
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
        # H-CICLO22-03: scope dedicado para CartVoucherView.
        # El endpoint revela existencia del voucher (VOUCHER_NOT_FOUND vs
        # validación fallida), lo que habilita enumeración de códigos.
        # 20/hour anón y 60/hour usuario reducen la ventana de brute-force
        # a menos de 1 código/3-min para anónimos.
        'voucher_apply':       '20/hour',
        # H-CICLO26-02: scopes para endpoints públicos de newsletter.
        # subscribe: evita spam de suscripciones y flooding de email.
        # newsletter_confirm: evita enumeración de tokens de confirmación.
        'newsletter_subscribe':   '10/hour',
        'newsletter_confirm':     '20/hour',
        # H-CICLO42-03: scope para baja de newsletter. Sin throttle el
        # endpoint permite enumeracion de tokens y bajas masivas automatizadas.
        'newsletter_unsubscribe': '10/hour',
        # H-CICLO42-04: scope para envio de preguntas publicas (UC-QST-01).
        # Sin throttle, cualquier visitante podia inundar la cola de moderacion.
        'question_ask':           '10/hour',
        # H-CICLO29-02: throttle para creacion de reseñas (UC-REV-02).
        # Sin este scope cualquier usuario autenticado podia spamear el
        # endpoint con distintos order_id. 10/hour permite resenar varios
        # productos de pedidos distintos sin limitar el uso legitimo.
        'review_create':        '10/hour',
        # H-CICLO43-01: throttle para CheckoutView (AllowAny, POST crea orden).
        # Sin throttle un atacante puede crear ordenes masivas bloqueando stock
        # y saturando la BD. 20/hour permite completar compras legitimas
        # (incluso invitados con varios intentos) sin abrir vector de abuso.
        'checkout':             '20/hour',
        # H-CICLO43-02: throttle para CartView/CartItemListView/CartItemDetailView.
        # Endpoints publicos (invitados y autenticados); sin throttle permiten
        # flooding del carrito. 120/hour cubre uso intensivo del SPA sin
        # restringir la experiencia de compra normal.
        'cart':                 '120/hour',
        # H-CICLO90-02: throttle para PaymentReturnView (AllowAny).
        # Sin throttle un atacante puede llamar el endpoint con order_numbers
        # arbitrarios y crear PaymentGatewayEvent rows en cada peticion, saturando
        # la BD de auditoria. 60/hour cubre el caso de uso legítimo (el gateway
        # redirige al comprador una sola vez por pago).
        'payment_return':       '60/hour',
        # H-CICLO108-05: throttle para InitiatePaymentView (IsAuthenticated).
        # Sin throttle un comprador (o un token robado) puede crear docenas de
        # preferencias en el gateway para la misma orden, consumiendo cuota de API.
        # 20/hour cubre reintentos legítimos sin abrir vector de abuso.
        'initiate_payment':     '20/hour',
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
        'Autenticación: sesión de servidor (cookie HttpOnly) via '
        'POST /api/v2/auth/login/\n'
        'Todos los endpoints bajo el prefijo /api/v2/'
    ),
    'VERSION': '1.0.0',
    'CONTACT': {
        'name': 'Equipo PracticaYoruba',
        'email': 'hola@practicayoruba.com',
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
        # OCP: importa los schema.py de las apps para registrar sus
        # OpenApiAuthenticationExtension (cookieAuth, ADR-018) ANTES de generar.
        'config.spectacular_hooks.register_app_schema_extensions',
    ],

    # --- Enums ---
    'ENUM_GENERATE_CHOICE_DESCRIPTION': True,
    'ENUM_SUFFIX': '',

    # D-032 T-4: cada modelo con campos 'status' o 'gateway' tiene su
    # propio choice set. Sin overrides drf-spectacular auto-resuelve
    # con sufijos hex (StatusFc3Enum, Gateway409Enum) — feo en clientes
    # generados. Cada entrada mapea EnumName -> path al choice set.
    #
    # IMPORTANTE: drf-spectacular resuelve estos paths con
    # deep_import_string, que solo soporta UN getattr extra tras el
    # ultimo modulo importable. Para una TextChoices ANIDADA en un modelo
    # (Model.Status) hay que apuntar a la CLASE (...Model.Status), NO a
    # ...Model.Status.choices (eso requiere dos getattr y resuelve a None
    # -> 'unable to load choice override' + duplication issues). El
    # resolver materializa .choices solo cuando el objeto es subclase de
    # Choices. Para una TextChoices a NIVEL DE MODULO (SubscriberStatus)
    # ambas formas funcionan; se mantiene .choices por legibilidad.
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
            'apps.notifications.models.ManualNotification.Status',
        'NewsletterSubscriberStatusEnum':
            'apps.newsletter.models.SubscriberStatus.choices',
        'QuestionStatusEnum':
            'apps.questions.models.QuestionStatus.choices',
        'SupportTicketStatusEnum':
            'apps.support.models.SupportTicket.Status',
        'ReturnRequestStatusEnum':
            'apps.returns.models.ReturnRequest.Status',
        # gateway fields (Payment vs PaymentGateway tienen choice sets
        # diferentes — el segundo agrega TEST sandbox)
        'PaymentGatewayChoiceEnum':
            'apps.payments.models.Payment.GATEWAYS',
        'PaymentGatewayConfigEnum':
            'apps.settings_app.models.PaymentGateway.GATEWAYS',
        # AudienceFilterEnum: alias para ManualNotification.RecipientType
        # que aparece en serializers diferentes con choice set identico
        'AudienceFilterEnum':
            'apps.notifications.models.ManualNotification.RecipientType',
        # `type` field collision: NotificationType es el unico choice set
        # de un campo llamado `type` que necesita nombre estable.
        'NotificationTypeEnum':
            'apps.notifications.models.NotificationType',
        # `reason` field collision: dos choice sets distintos comparten el
        # nombre de campo `reason` — devolucion vs ajuste de inventario.
        'ReturnReasonEnum':
            'apps.returns.models.ReturnRequest.Reason',
        'StockAdjustmentReasonEnum':
            'apps.inventory.serializers.ADJUSTMENT_REASONS',
    },
}

# CORS — origins must be set explicitly via env var in each environment.
# Empty default means all cross-origin requests are rejected unless overridden
# (e.g., development.py sets CORS_ALLOWED_ORIGINS for localhost).
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='', cast=Csv())
CORS_ALLOW_CREDENTIALS = True

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
        # Veredictos del CookieGovernanceMiddleware (modo auditoria, ADR-018).
        'cookie_governance': {'handlers': ['console', 'file'], 'level': 'INFO'},
    },
}

SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Auth por sesion (ADR-018, DEC-STF-AUTH-COOKIE) — sesion como unica auth web.
# La cookie de sesion es HttpOnly y SameSite=Lax (mismo origin en dev via el
# proxy de webpack y en prod mismo dominio). El endurecimiento a __Host- +
# Secure + SameSite=Strict vive en production.py; ese SameSite=Strict es la
# defensa CSRF que reemplaza al token (ver DEFAULT_AUTHENTICATION_CLASSES).
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'

# CSRF: NO se usa token CSRF. La auth por sesion esta exenta
# (CsrfExemptSessionAuthentication) y la defensa CSRF es SameSite=Strict +
# __Host- de la cookie de sesion. Por eso NO se define CSRF_USE_SESSIONS ni se
# emite cookie/token CSRF: no hay plumbing de token que el SPA deba mantener.

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

# W036: MariaDB no soporta UniqueConstraint con condition=.
# Afecta CartItem (T-DEV-3) y WishlistItem (T-DEV-4).
# La unicidad se garantiza a nivel de aplicación:
#   - CartItem: get_or_create() dentro de transaction.atomic()
#   - WishlistItem: pre-check + captura de IntegrityError → 409
# suppress_warnings en class Meta no está disponible en Django 6.0.5;
# SILENCED_SYSTEM_CHECKS sigue siendo el mecanismo correcto.
SILENCED_SYSTEM_CHECKS = ['models.W036']
