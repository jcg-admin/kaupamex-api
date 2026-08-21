"""URLs — addons.authz_totp (gestión del 2FA del usuario, /api/v2/authz/totp/)."""
from django.urls import path

from addons.authz_totp.controllers.main import (
    totp_confirm,
    totp_disable,
    totp_login,
    totp_recovery_codes,
    totp_setup,
    totp_status,
)

urlpatterns = [
    path('', totp_status, name='totp-status'),
    # El segundo paso del LOGIN, no gestión de cuenta — es la única ruta de
    # este módulo que no exige usuario.
    #
    # NO confundirla con `TOTP_SECOND_STEP_URL` (`models/res_users.py:123`),
    # que es lo que `_mfa_url()` publica en el 401: aquélla es la PANTALLA del
    # SPA y ésta es la API que esa pantalla llama. En la referencia son una
    # sola cosa —`/web/login/totp` sirve el formulario y recibe su POST—
    # porque su cliente es una página servida por el mismo proceso.
    path('login/', totp_login, name='totp-login'),
    path('setup/', totp_setup, name='totp-setup'),
    path('confirm/', totp_confirm, name='totp-confirm'),
    path('disable/', totp_disable, name='totp-disable'),
    path('recovery-codes/', totp_recovery_codes, name='totp-recovery-codes'),
]
