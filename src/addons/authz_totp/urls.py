"""URLs — addons.authz_totp (gestión del 2FA del usuario, /api/v2/authz/totp/)."""
from django.urls import path

from addons.authz_totp.views import (
    totp_confirm,
    totp_disable,
    totp_recovery_codes,
    totp_setup,
    totp_status,
)

urlpatterns = [
    path('', totp_status, name='totp-status'),
    path('setup/', totp_setup, name='totp-setup'),
    path('confirm/', totp_confirm, name='totp-confirm'),
    path('disable/', totp_disable, name='totp-disable'),
    path('recovery-codes/', totp_recovery_codes, name='totp-recovery-codes'),
]
