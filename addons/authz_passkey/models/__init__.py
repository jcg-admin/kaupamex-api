# Adaptado de Odoo Community `auth_passkey/models/__init__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
#
# La referencia importa 3 archivos; el mapa completo, sin omisiones:
#
#   auth_passkey_key.py       → auth_passkey_key.py (PasskeyKey + los
#                               helpers WebAuthn start/verify de auth y
#                               registro; el wizard transient
#                               auth.passkey.key.create es el POST de
#                               registro en ../views.py)
#   res_users.py              → el o2m `auth_passkey_key_ids` es el reverso
#                               de la FK (related_name='passkeys');
#                               _login/_check_credentials tipo `webauthn`
#                               viven en ../backends.py; la rotación del
#                               session token (_get_session_token_*) es del
#                               mecanismo de sesión de Odoo — la sesión
#                               Django no deriva su token de campos, no
#                               aplica.
#   res_users_identitycheck.py → NO portado (gap nombrado): permite usar la
#                               passkey como método de re-autenticación en
#                               el identity check; el análogo es abrir la
#                               ReauthSession de authz_reauth con passkey —
#                               integración pendiente sobre el endpoint
#                               /api/v2/authz/reauth/.
#
# ../mobile_utils.py (hashes APK de la app móvil Odoo) NO se porta: son los
# orígenes válidos de SU app Android.
from addons.authz_passkey.models.auth_passkey_key import PasskeyKey  # noqa: F401
