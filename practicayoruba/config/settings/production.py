from .base import *
from decouple import config, Csv  # importación explícita — no depender del * de base.py

# Sobreescribe el default inseguro de base.py — falla explícitamente si no está configurada.
SECRET_KEY = config('SECRET_KEY')

DEBUG = False
SESSION_COOKIE_SECURE   = True
SESSION_COOKIE_HTTPONLY = True   # default de Django pero se fija explicitamente
CSRF_COOKIE_SECURE      = True
# H-CICLO82-04: Django default de CSRF_COOKIE_HTTPONLY es False, lo que
# permite que JavaScript lea la cookie CSRF via document.cookie.  Para una
# API DRF con JWT (sin formularios Django) la cookie CSRF no necesita ser
# legible por JS — el valor se transmite solo en el header X-CSRFToken que
# el browser incluye automaticamente desde la cookie HttpOnly en requests
# cross-origin con credentials. Marcarla HttpOnly cierra el vector de robo
# de token CSRF via XSS.
CSRF_COOKIE_HTTPONLY    = True
SECURE_SSL_REDIRECT     = True

# H-CICLO25-01: activar explícitamente el middleware de Django que emite
# "X-Content-Type-Options: nosniff".  SecurityMiddleware lo respeta solo
# cuando esta bandera es True — el default de Django es False, por lo que
# sin este ajuste ningún response de la API incluye el header, abriendo la
# puerta a ataques de MIME-type sniffing (p.ej. subida de avatar .png que
# el browser re-interpreta como script ejecutable).
SECURE_CONTENT_TYPE_NOSNIFF = True

# H-CICLO20-03: HSTS via Django SecurityMiddleware además del header de
# Apache. Garantiza que el header se emita aunque la petición llegue a
# Django sin pasar por mod_headers (p.ej. proxies internos, health checks
# directos al puerto WSGI). Valor alineado con el max-age del vhost Apache.
SECURE_HSTS_SECONDS = 31536000          # 1 año
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# --- Proxy SSL (Apache + mod_wsgi) -------------------------------------
# Apache termina SSL y reenvía a Django via HTTP interno.
# Sin este header, SECURE_SSL_REDIRECT=True produce un bucle infinito
# de redirects 301 porque Django no puede detectar que la conexión
# original era HTTPS. Apache debe setear el header correspondiente:
#   RequestHeader set X-Forwarded-Proto "https"
# (ver config/apache/practicayoruba-https.conf en PracticaYoruba-server)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# H-CICLO81-02: habilitar USE_X_FORWARDED_HOST para que Django use el
# header X-Forwarded-Host enviado por Apache en lugar del hostname interno
# del servidor WSGI. Sin este flag request.build_absolute_uri() genera URLs
# con el hostname interno (ej. 127.0.0.1) en lugar del dominio publico,
# rompiendo los download_url de importacion de inventario y cualquier
# enlace absoluto construido por la API. Apache debe enviar el header:
#   RequestHeader set X-Forwarded-Host "%{HTTP_HOST}s"
# (ya documentado en practicayoruba-https.conf).
USE_X_FORWARDED_HOST = True

# --- Hosts permitidos -------------------------------------------------------
# base.py define ALLOWED_HOSTS con default 'localhost,127.0.0.1'.
# init-env.sh copia ese default al .env sin incluir el dominio público.
# Apache pasa Host: <dominio> a Django → DisallowedHost → HTTP 400.
# Sobreescribir con un default de producción que incluye practicayoruba.mx.
# Si el .env tiene ALLOWED_HOSTS explícito, decouple lo usa en su lugar.
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='practicayoruba.mx,localhost,127.0.0.1',
    cast=Csv(),
)

# --- UI React (SPA) ----------------------------------------------------
# Ruta al build de producción del UI (resultado de: npm run build).
# Usada por la vista serve_spa en config/urls.py para servir index.html.
#
# Iniciativa: configurar-ui-dist-en-deploy (H-UID-1, H-UID-2). Default
# previo ``/opt/practicayoruba/ui/dist`` era ruta histórica obsoleta
# para el layout WSL2/VPS canónico. Cambiado a string vacío — centinela
# para que ``serve_spa`` se desactive (urls.py:130 ya tiene el guard
# ``if getattr(settings, 'UI_DIST', None):``).
#
# Configurar en ``practicayoruba/.env`` la ruta real:
#   UI_DIST=/srv/repos/ecom/e-commerce-ui/dist   (WSL2 canónico)
UI_DIST = config('UI_DIST', default='')

# --- Email -----------------------------------------------------------------
# Puerto saliente requerido en el VPS: 587/tcp (SMTP STARTTLS).
# UFW ya permite todo el tráfico saliente (default allow outgoing) —
# no requiere regla adicional.
#
# Variables requeridas en el .env de producción:
#   EMAIL_HOST          ej: smtp.sendgrid.net
#   EMAIL_HOST_USER     ej: apikey  (SendGrid usa "apikey" como usuario)
#   EMAIL_HOST_PASSWORD ej: SG.xxxxxxx...
#
# Variables opcionales (defaults válidos para la mayoría de proveedores):
#   EMAIL_PORT          default: 587
#   EMAIL_USE_TLS       default: True  (STARTTLS en puerto 587)
EMAIL_BACKEND     = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST        = config('EMAIL_HOST',        default='')
EMAIL_PORT        = config('EMAIL_PORT',        default=587,  cast=int)
EMAIL_USE_TLS     = config('EMAIL_USE_TLS',     default=True, cast=bool)
EMAIL_HOST_USER   = config('EMAIL_HOST_USER',   default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')

# URL base del frontend — usada en tokens_email.py para construir los
# enlaces de verificación de cuenta y recuperación de contraseña.
# Debe coincidir con el dominio público de la aplicación.
FRONTEND_URL = config('FRONTEND_URL', default='https://practicayoruba.mx')

# H-CICLO84-03: elevar nivel de log a WARNING en produccion.
# base.py define ambos loggers en INFO, lo que es apropiado para
# desarrollo pero excesivo en produccion: cada peticion HTTP, cada
# query lenta y cada operacion de negocio genera una entrada en el
# archivo rotativo, llenando disco y exponiendo rutas internas,
# parametros y patrones de uso en los logs. WARNING suprime mensajes
# informativos y preserva solo advertencias y errores.
LOGGING['loggers']['django']['level'] = 'WARNING'
LOGGING['loggers']['apps']['level']   = 'WARNING'

# --- Media (uploads de usuario) --------------------------------------------
# base.py usa BASE_DIR/'media' (dentro del árbol del repo) — correcto en
# dev/test. En producción los uploads de usuario deben vivir fuera del
# árbol versionado: un git clean o re-clone no debe borrar fotos subidas.
# RF-2 (alcance-agregar-fotos-reviews): acción de deploy requerida:
#   sudo mkdir -p /opt/practicayoruba/media
#   sudo chown www-data:www-data /opt/practicayoruba/media
MEDIA_ROOT = Path(config('MEDIA_ROOT', default='/opt/practicayoruba/media'))
