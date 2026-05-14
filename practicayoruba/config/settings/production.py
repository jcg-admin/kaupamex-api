from .base import *
from decouple import config  # importación explícita — no depender del * de base.py

DEBUG = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

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
# ALLOWED_HOSTS debe incluir el dominio real en el .env de producción.
UI_DIST = config('UI_DIST', default='/opt/practicayoruba/ui/dist')
