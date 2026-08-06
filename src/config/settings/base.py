from pathlib import Path
from datetime import timedelta
from decouple import config, Csv
import certifi

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')
# Dedicated key for MFA/TOTP secret encryption at rest (Fernet).
# Decoupled from SECRET_KEY so rotating SECRET_KEY does NOT lock out
# every 2FA user (analisis-utilidad-totp-nativa-kaupamex, T-PLT-33).
MFA_ENCRYPTION_KEY = config('MFA_ENCRYPTION_KEY', default=SECRET_KEY)
# DEC-12: vida (segundos) de una sesion reautenticada (elevacion de confianza,
# NO de privilegios). Migrada a SystemParameter L2 ('authz.reauth_ttl',
# H-API-CFG-02) — era un tunable operativo global con default= cableado en
# codigo; ahora editable en caliente sin redeploy. Ver
# addons.authz.services._reauth_ttl().
DEBUG = config('DEBUG', default=False, cast=bool)

# Seguridad (H-11): el admin nativo de Django se monta SOLO si esta bandera
# esta activa. Default = DEBUG -> en produccion (DEBUG=False) queda APAGADO y
# no expone un login de fuerza bruta en /admin/. El backoffice del producto es
# el admin React + DRF (/api/v2/admin/), no el admin de Django.
DJANGO_ADMIN_ENABLED = config('DJANGO_ADMIN_ENABLED', default=DEBUG, cast=bool)

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
    'core',
    'addons.bus',
    'addons.uom',
    'addons.product',
    'addons.stock',
    'addons.stock_account',
    'addons.stock_landed_costs',
    'addons.product_expiry',
    'addons.loyalty',
    'addons.website_sale',
    'addons.website_sale_wishlist',
    'addons.sale',
    'addons.sales_team',
    'addons.sale_stock',
    'addons.sale_loyalty',
    'addons.sale_loyalty_delivery',
    'addons.sale_management',
    'addons.sale_service',
    'addons.sale_margin',
    'addons.crm',
    'addons.sale_crm',
    'addons.sms',
    'addons.sale_sms',
    'addons.product_matrix',
    'addons.sale_product_matrix',
    'addons.sale_stock_margin',
    'addons.sale_stock_product_expiry',
    'addons.project',
    'addons.sale_project',
    'addons.purchase',
    'addons.sale_purchase',
    'addons.mrp',
    'addons.mrp_subcontracting',
    'addons.sale_mrp',
    'addons.sale_mrp_margin',
    'addons.payment',
    'addons.payment_aps',
    'addons.payment_authorize',
    'addons.payment_custom',
    'addons.payment_demo',
    'addons.payment_mercado_pago',
    'addons.payment_paypal',
    'addons.payment_stripe',
    'addons.helpdesk',
    'addons.mass_mailing',
    'addons.website_mass_mailing',
    'addons.delivery',
    'addons.rating',
    'addons.website',
    'addons.auto_backup',
    'addons.base',
    'addons.base_setup',
    'addons.observability',
    'addons.mail',
    'addons.base_address_extended',
    'addons.base_geolocalize',
    'addons.base_vat',
    'addons.base_bank',
    'addons.authz',
    'addons.authz_audit',
    'addons.authz_reauth',
    'addons.authz_password_policy',
    'addons.authz_signup',
    'addons.authz_totp',
    'addons.authz_ldap',
    'addons.authz_oauth',
    'addons.authz_totp_mail',
    'addons.authz_passkey',
    'addons.web',
    'addons.portal',
    'addons.sale_subscription',
    'addons.hr',
    'addons.account',
    # Familias nuevas de la Ola 0 de `integrar-familia-account-completa`:
    # dependencias que la referencia declara y nuestro árbol no tenía. Se
    # portan completas, no recortadas a la superficie que account toca.
    'addons.certificate',
    'addons.onboarding',
    'addons.analytic',
    'addons.fleet',
    'addons.resource',
    'addons.digest',
]

AUTH_USER_MODEL = 'base.ResUsers'

# Cadena de autenticación — el equivalente Django de la cadena super()._login
# de la referencia (auth_ldap/models/res_users.py:13-32): el password local
# intenta primero (ModelBackend, el default implícito hasta ahora — se declara
# explícito al federar) y LDAP es el fallback. Sin python-ldap instalado
# (extra `ldap`), LdapBackend degrada devolviendo None y la cadena se comporta
# como antes.
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'addons.authz_ldap.models.backends.LdapBackend',
    # ≙ credential type 'oauth_token' de auth_oauth (_check_credentials):
    # solo atiende el kwarg oauth_token, invisible para logins con password.
    'addons.authz_oauth.models.backends.OauthTokenBackend',
    # ≙ credential type 'webauthn' de auth_passkey: solo atiende el kwarg
    # webauthn_response.
    'addons.authz_passkey.models.backends.PasskeyBackend',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # RequestLogMiddleware (DEC-LOG-02): cobertura universal request->DB. Va
    # cerca del tope para medir la duracion completa; su process_response corre
    # tras get_response, cuando request.user y resolver_match ya estan puestos.
    # Vive en addons.observability (addon net-new, DEC-12) desde el slice 3 de
    # adoptar-arquitectura-server-service-odoo (antes core.middleware.request_log).
    'addons.observability.middleware.RequestLogMiddleware',
    # CookieGovernanceMiddleware va sobre Session/CSRF: su process_response
    # (orden inverso) corre despues de que aquellas ponen sus cookies, para
    # observarlas/gobernarlas. Fase 1 = auditoria (COOKIE_GOVERNANCE_ENFORCE
    # por defecto False). Ver iniciativa migrar-auth-sesion-cookie-httponly.
    'core.middleware.cookie_governance.CookieGovernanceMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'addons.base.models.ir_http.CompanyContextMiddleware',
    # DeviceLogMiddleware: el punto donde la referencia registra el dispositivo
    # de la peticion (check_session -> res.device.log._update_device,
    # odoo19c: odoo/service/security.py:23,31). Va DESPUES de Session y
    # Authentication: necesita session_key y request.user. Trazado throttled a
    # una fila por dispositivo por hora; nunca rompe la respuesta.
    'addons.base.models.res_device.DeviceLogMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # H-CART-01 Fase 2: fija la cookie httpOnly cart_token para carritos
    # anonimos. Va por DEBAJO de CookieGovernanceMiddleware para que el
    # process_response de aquel (orden inverso) observe la cookie de carrito.
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

# Conexion DB — PostgreSQL (iniciativa migrar-motor-mariadb-a-postgresql).
# Socket Unix preferido en dev local; en produccion OVH (VM1→VM3) TCP con SSL.
# Ver docs/source/normativa/procedimientos/proc-ejecutar-pruebas.rst.
#
# Dos claves de la era mysqlclient NO tienen equivalente y se retiran, no se
# traducen — escribir un sustituto inventado seria peor que no tenerlas:
#
#   ``charset='utf8mb4'``  El encoding es de la DATABASE, no de la conexion ni
#                          de la tabla. Lo fija ``CREATE DATABASE … ENCODING``
#                          (el provisioner de db lo hace con TEMPLATE
#                          template0). No hay nada que declarar por conexion.
#   ``init_command``       ``SET sql_mode='STRICT_TRANS_TABLES'`` endurecia un
#   ``SET sql_mode=…``     motor que por defecto es laxo (truncaba en vez de
#                          fallar). PostgreSQL ya rechaza el dato que no cabe:
#                          no hay modo laxo que endurecer.
_DB_OPTIONS = {}
# SSL: por defecto verifica el cert del server contra CAs publicas (certifi),
# valido para la DB productiva (Let's Encrypt; VM3 TCP + require_secure_transport).
# DB_SSL_MODE=DISABLED apaga TLS para entornos con cert self-signed o socket
# local (contenedor/CI) sin afectar produccion. Paridad con testing.py
# (DB_QA_SSL_MODE): antes 'ssl' estaba hardcodeado y rompia el socket local con
# "certificate verify failed" (H-API-LOG-04).
#
# DB_SSL_MODE y DB_SOCKET son TOGGLES OPCIONALES: su ausencia tiene un
# significado definido (verificar cert contra CAs publicas / fallback TCP), por
# el guard ``if _X:`` de abajo. Llevan ``default=''`` a proposito — a diferencia
# de las claves de CONEXION (NAME/USER/PASSWORD/HOST/PORT) que SI son sin
# ``default=`` por SOL-087 (fail-loud). Requerir estos toggles rompia el import
# de settings en cualquier entorno sin la envvar (CI sin ``.env``: base.py
# construye ``DATABASES`` al import antes de que testing.py lo reemplace).
_DB_SSL_MODE = config('DB_SSL_MODE', default='')
if _DB_SSL_MODE:
    _DB_OPTIONS['sslmode'] = _DB_SSL_MODE.lower()
else:
    _DB_OPTIONS['sslmode'] = 'verify-full'
    _DB_OPTIONS['sslrootcert'] = certifi.where()
# El socket NO es una opcion en libpq: es el HOST. Cuando ``host`` empieza por
# ``/``, libpq lo interpreta como el DIRECTORIO donde vive el socket y NO abre
# TCP — el puerto pasa a nombrar el archivo (``.s.PGSQL.<port>``), no un puerto
# de red. Por eso ``DB_SOCKET`` aqui vale el directorio
# (``/var/run/postgresql``), no la ruta del archivo como en mysqlclient.
# Ver H-API-305.
_DB_SOCKET = config('DB_SOCKET', default='')

# Config de conexión — SIN ``default=`` (SOL-087, directiva ejecutor
# 2026-07-16): toda la configuración vive en ``.env`` (12-factor). Falla
# ruidoso si una clave falta, en vez de esconder un valor mágico en el código.
# La infraestructura la nombra el operador L0 (Kaupamex), no una empresa L1;
# cada L1 queda como fila de la tabla ``res_company``, creada por bootstrap
# (``BOOTSTRAP_COMPANY_CODE`` + ``company_create``), no por código.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': _DB_SOCKET or config('DB_HOST'),
        'PORT': config('DB_PORT'),
        'OPTIONS': _DB_OPTIONS,
    }
}

# Multi-DB DB-per-company (SOL-091, T-091-05). Roster EXPLÍCITO de bases de
# empresa: vacío = N=1 (sólo ``default``). NO se descubre por
# ``information_schema`` en el import de settings (chicken-and-egg con
# ``connections``; una DB fresca/CI aún no existe) — el roster es 12-factor y el
# descubrimiento runtime vive en ``service.db.list_company_db_names``. El
# ``default=''`` es de un roster opcional (feature-off), no de un secreto de
# conexión (SOL-087 aplica al bloque ``default`` de arriba).
from service.db import install_company_aliases  # noqa: E402

_MULTIDB_COMPANY_DBS = config('MULTIDB_COMPANY_DATABASES', default='', cast=Csv())
install_company_aliases(DATABASES, list(_MULTIDB_COMPANY_DBS))

# Router DB-per-company: enruta dominio→company_<N>_db, control L0→default. El
# fail-closed duro (dominio sin empresa bajo N>1) se activa solo cuando el roster
# de arriba puebla aliases ``company_*`` (ver ``orm.routers``).
DATABASE_ROUTERS = ['orm.routers.CompanyDatabaseRouter']

# Plano de control L0 (vive siempre en ``default``, no se particiona por empresa).
# ``addons.base`` (addon fundacional, ``SystemParameter`` L2 global) es config de
# instancia, no per-empresa (SOL-090): debe rutear a ``default`` también bajo N>1.
# ``observability`` (``RequestLog``, DEC-12) es telemetria global de la instancia,
# no per-empresa, por lo que rutea igual que ``base``.
MULTIDB_CONTROL_PLANE_APPS = ('sessions', 'contenttypes', 'base', 'observability', 'base_address_extended', 'base_geolocalize')

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    # Longitud mínima editable en caliente (L2) — adaptación de
    # authz_password_policy de Odoo. Reemplaza a MinimumLengthValidator (que
    # cablea min_length=8 en settings) por la variante configurable en
    # SystemParameter (default 8; sin regresión). Ver addons.authz_password_policy.
    {'NAME': 'addons.authz_password_policy.validators.ConfigurablePasswordPolicyValidator'},
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

# Dirección remitente por defecto de plataforma (L0, Kaupamex). Fallback
# neutral env-overridable: lo usa Django implícitamente (send_mail sin
# from_email) y el alertamiento de backups (infra L0, sin dimensión de
# empresa). NO es la verdad per-tenant — el remitente transaccional de cada
# tenant vive en L3 (ver abajo). Sobrescribir en production.py via decouple.
DEFAULT_FROM_EMAIL = 'noreply@kaupamex.com'

# Destinatario de alertas operativas (UC-ADM-05: backup fallido). Migrado a
# SystemParameter L2 ('backup.alert_email', H-API-CFG-01) — tenia default=
# stale (practicayoruba.com); ahora editable en caliente. Ver
# addons.auto_backup.controllers.main._notify_backup_failed().
#
# Buzones por propósito en VM2 (Postfix + Cyrus). Contacto y newsletter usan
# su buzón monitoreado para que la conversación llegue a un humano y las
# respuestas no caigan en un buzón no-reply.
#
# Los remitentes de correo per-empresa migraron a L3
# (``addons.base.CompanySetting`` — per-empresa, FK ``company`` +
# record rules ``ir_rule``): ya NO son settings de Django.
#
# - CONTACT_FROM_EMAIL/CONTACT_NOTIFY_EMAIL/NEWSLETTER_FROM_EMAIL → SOL-090
#   slice 3.
# - DEFAULT_FROM_EMAIL (remitente no-reply transaccional: auth, órdenes,
#   envíos, devoluciones, soporte) → follow-up #199, clave
#   ``notifications.from_email``.
#
# Los consumidores (``addons.crm.controllers``,
# ``addons.mass_mailing.controllers``, ``addons.mail.models``,
# ``addons.website_mass_mailing.controllers``) leen
# ``CompanySetting.get_setting('<key>', <fallback neutral>)`` bajo la empresa
# resuelta (ambiente para flujos autenticados; ``company=user.company_id``
# explícito para auth pre-login); el fallback ES neutral (nivel Kaupamex,
# ``*@kaupamex.com``) — el L1 de ejemplo es una empresa entre potencialmente
# varias, así que su remitente propio se declara en el bootstrap
# (``manage.py company_create <code> --setting clave=valor``), NO como
# constante de código. Cierra H-CFG-IMPL-10 + H-CFG-IMPL-13. Ver
# addons.base.models.CompanySetting y
# hallazgos-implementar-systemparameter-l2.

# Bootstrap de la primera empresa L1 (DEC-3 de ``tenants-sin-clases-en-codigo``).
# La app NO nombra "el founder" por código en runtime: la empresa inicial se
# declara aquí (12-factor, ``.env``) y la crea ``company_create``. Vacío = la
# instalación no siembra ninguna empresa por sí sola.
BOOTSTRAP_COMPANY_CODE = config('BOOTSTRAP_COMPANY_CODE', default='')
BOOTSTRAP_COMPANY_NAME = config('BOOTSTRAP_COMPANY_NAME', default='')

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
        'addons.base.authentication.CsrfExemptSessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # SOL-011 / ADR-019: envuelve el handler de DRF para sellar exception_class
    # + error_detail (scrubbed) en RequestLog sin cambiar el cuerpo de error
    # (conserva la clave canonica ``codigo_error``). No bloqueante (DEC-LOG-04).
    'EXCEPTION_HANDLER': 'addons.observability.exception_handling.custom_exception_handler',
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
    'TITLE': 'Kaupamex API',
    'DESCRIPTION': (
        'API REST de Kaupamex — plataforma multi-company de comercio\n'
        'electrónico. PracticaYoruba es su L1 de ejemplo, no la\n'
        'plataforma.\n\n'
        'Autenticación: sesión de servidor (cookie HttpOnly) via '
        'POST /api/v2/auth/login/\n'
        'Todos los endpoints bajo el prefijo /api/v2/'
    ),
    'VERSION': '1.0.0',
    # Contacto del schema OpenAPI = operador de la plataforma (L0, Kaupamex):
    # la API es infraestructura de plataforma (un solo codebase Django sirve a
    # todos los tenants), evaluada estáticamente al generar el schema — sin
    # dimensión de empresa. Antes reusaba el buzón L1 de ejemplo
    # (``hola@practicayoruba.com``); es config de plataforma, no per-tenant
    # (DEC-KX-05, follow-up #199). El TITLE/DESCRIPTION **ya no** llevan el
    # branding del L1: la API publicada es la de la plataforma, y llamarla
    # "PracticaYoruba API" la confundía con su tenant de ejemplo. La decisión
    # de producto que este comentario dejaba pendiente la tomó el ejecutor el
    # 2026-08-06; el schema QA ya se llamaba ``kaupamex_qa``, así que el
    # título era el último resto del nombre viejo en la superficie publicada.
    'CONTACT': {
        'name': 'Equipo Kaupamex',
        'email': 'soporte@kaupamex.com',
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
        'PaymentStatusEnum':
            'addons.payment.models.Payment.STATUSES',
        'RefundStatusEnum':
            'addons.payment.models.Refund.STATUSES',
        'ReviewStatusEnum':
            'addons.rating.models.Review.STATUSES',
        'ShipmentGuideStatusEnum':
            'addons.delivery.models.ShipmentGuide.STATUSES',
        'StaticPageVersionStatusEnum':
            'addons.website.models.StaticPageVersion.STATUS_CHOICES',
        'NotificationStatusEnum':
            'addons.mail.models.manual_notification.ManualNotification.Status',
        'SupportTicketStatusEnum':
            'addons.helpdesk.models.SupportTicket.Status',
        'ReturnRequestStatusEnum':
            'addons.stock.models.ReturnRequest.Status',
        # gateway fields (Payment vs PaymentGateway tienen choice sets
        # diferentes — el segundo agrega TEST sandbox)
        'PaymentGatewayChoiceEnum':
            'addons.payment.models.Payment.GATEWAYS',
        'PaymentGatewayConfigEnum':
            'addons.payment.models.PaymentGateway.GATEWAYS',
        # AudienceFilterEnum: alias para ManualNotification.RecipientType
        # que aparece en serializers diferentes con choice set identico
        'AudienceFilterEnum':
            'addons.mail.models.manual_notification.ManualNotification.RecipientType',
        # `type` field collision: NotificationType es el unico choice set
        # de un campo llamado `type` que necesita nombre estable.
        'NotificationTypeEnum':
            'addons.mail.models.notification_inbox.NotificationType',
        # `reason` field collision: dos choice sets distintos comparten el
        # nombre de campo `reason` — devolucion vs ajuste de inventario.
        'ReturnReasonEnum':
            'addons.stock.models.ReturnRequest.Reason',
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
        # SOL-011 (DEC-LOG-02): persiste logger.* + django.request (5xx) a la
        # tabla ir_logging (IrLogging) via DatabaseLogHandler. PII-safe (scrubber Nivel 1),
        # no bloqueante y anti-recursion (se excluye django.db). testing.py
        # sobreescribe LOGGING con NullHandler, asi que este handler NO corre
        # durante la suite (el handler se prueba directamente).
        'db': {'class': 'tools.logging_handlers.DatabaseLogHandler',
               'level': 'INFO'},
    },
    'loggers': {
        'django': {'handlers': ['console', 'file', 'db'], 'level': 'INFO'},
        'apps':   {'handlers': ['console', 'file', 'db'], 'level': 'INFO'},
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
