"""URLs — addons.authz_totp (gestión del 2FA del usuario, /api/v2/authz/totp/)."""
from django.urls import path

from addons.authz_totp.views import (
    TotpConfirmView,
    TotpDisableView,
    TotpSetupView,
    TotpStatusView,
)

urlpatterns = [
    path('', TotpStatusView.as_view(), name='totp-status'),
    path('setup/', TotpSetupView.as_view(), name='totp-setup'),
    path('confirm/', TotpConfirmView.as_view(), name='totp-confirm'),
    path('disable/', TotpDisableView.as_view(), name='totp-disable'),
]
