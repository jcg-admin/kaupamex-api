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

# --- Email (Mailpit) -------------------------------------------------------
# Mailpit intercepta todos los emails y los expone en http://localhost:8025.
# No envía a internet — el desarrollador puede verificar asunto, destinatario
# y cuerpo del email en la UI web de Mailpit.
# Arrancar Mailpit: sudo bash provisioners/smtp/setup_mailpit.sh
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = '127.0.0.1'
EMAIL_PORT = 1025
EMAIL_USE_TLS = False
EMAIL_USE_SSL = False
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''

# URL base del frontend para construir los enlaces en los emails de
# verificación de cuenta y recuperación de contraseña.
FRONTEND_URL = 'http://localhost:3001'

CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:3001',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:3001',
]
