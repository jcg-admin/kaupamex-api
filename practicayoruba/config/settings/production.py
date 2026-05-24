from .base import *
from decouple import config  # importación explícita — no depender del * de base.py

# Sobreescribe el default inseguro de base.py — falla explícitamente si no está configurada.
SECRET_KEY = config('SECRET_KEY')

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

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

# --- Archivos estáticos -------------------------------------------------
# STATIC_ROOT es requerido en producción para que collectstatic funcione.
# Apache sirve /static/ directamente desde este directorio.
# Ejecutar tras cada deploy: python manage.py collectstatic --noinput
STATIC_ROOT = BASE_DIR / 'staticfiles'

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
#   UI_DIST=/srv/repos/ecom/ui/dist   (WSL2 canónico)
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
