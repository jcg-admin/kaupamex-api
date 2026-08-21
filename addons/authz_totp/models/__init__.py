# Paquete models/ — espejo del layout de `auth_totp/models/` (Odoo, LGPL-3).
#
# Mapa referencia → aquí, sin omisiones (desagrupado de un models.py plano,
# H-API-231):
#
#   totp.py                       → totp.py (algoritmo TOTP/hotp, verbatim)
#   res_users.py                  → res_users.py — lo que el 2FA cuelga del
#                                   usuario (_mfa_type/_mfa_url/totp_enabled);
#                                   su docstring lleva el mapa de los 24
#                                   símbolos de la fuente, uno por uno
#   res_users.py (totp_secret     → totp_secret.py — el secreto vive en tabla
#     NO_ACCESS en res.users)       propia OneToOne, no en el usuario
#   auth_totp.py                  → auth_totp.py — `auth_totp.device`, el
#     (dispositivos de confianza,   dispositivo de confianza. Hereda de
#     hereda res.users.apikeys)     `_ResUsersApikeysBase` (base abstracta de
#                                   `res.users.apikeys`), que es la forma
#                                   Django de la herencia por prototipo
#   auth_totp_rate_limit_log.py   → NO portado: rate-limit de intentos TOTP
#                                   (gap nombrado en el mismo hallazgo)
#   (sin contraparte)             → totp_recovery_code.py — endurecimiento
#                                   propio (0 hits de "recovery" en la ref)
from addons.authz_totp.models.auth_totp import AuthTotpDevice  # noqa: F401
from addons.authz_totp.models.totp_recovery_code import TotpRecoveryCode  # noqa: F401
from addons.authz_totp.models.totp_secret import TotpSecret  # noqa: F401
