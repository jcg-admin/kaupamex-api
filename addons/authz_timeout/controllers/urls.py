"""URLs — ``addons.authz_timeout`` (candado por tiempo, ``/api/v2/authz/timeout/``).

Las tres rutas de ``auth_timeout/controllers/main.py``, con la misma
separación que la fuente: la que **describe** el estado del candado y la que
**recibe** la credencial son rutas distintas, no dos verbos de una.

``check-identity/`` es el valor de ``CHECK_IDENTITY_URL`` (``../exceptions.py``),
que el 403 ``CHECK_IDENTITY_REQUIRED`` lleva en su cuerpo — el análogo del
``request.redirect_query`` que la fuente emite para su cliente de páginas.
"""
from django.urls import path

from addons.authz_timeout.controllers.main import (
    check_identity_state,
    check_identity_submit,
    send_totp_mail_code_view,
)

app_name = 'authz_timeout'

urlpatterns = [
    path('check-identity/', check_identity_state, name='check-identity'),
    path('session/check-identity/', check_identity_submit,
         name='check-identity-submit'),
    path('send-totp-mail-code/', send_totp_mail_code_view,
         name='send-totp-mail-code'),
]
