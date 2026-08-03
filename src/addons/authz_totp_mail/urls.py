"""URLs — addons.authz_totp_mail (2FA por correo + invitación)."""
from django.urls import path

from addons.authz_totp_mail.views import invite, send_code, verify_code

app_name = 'authz_totp_mail'

urlpatterns = [
    path('send-code/', send_code, name='send-code'),
    path('verify-code/', verify_code, name='verify-code'),
    path('invite/', invite, name='invite'),
]
