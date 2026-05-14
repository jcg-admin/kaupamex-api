from .base import *

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

INSTALLED_APPS += ['django_extensions']

REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
    'rest_framework.renderers.JSONRenderer',
    'rest_framework.renderers.BrowsableAPIRenderer',
]

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_SSL_REDIRECT = False

# --- Email -----------------------------------------------------------------
# console.EmailBackend imprime cada email completo en la terminal del
# servidor de desarrollo. No envía nada — el desarrollador puede verificar
# el asunto, destinatario y cuerpo del email sin necesitar un proveedor SMTP.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# URL base del frontend para construir los enlaces en los emails de
# verificación de cuenta y recuperación de contraseña.
FRONTEND_URL = 'http://localhost:3001'
