# Paquete models/ — espejo del layout de `auth_totp/models/` (Odoo, LGPL-3).
#
# Mapa referencia → aquí, sin omisiones (desagrupado de un models.py plano,
# H-API-231):
#
#   totp.py                       → totp.py (algoritmo TOTP/hotp, verbatim)
#   res_users.py (totp_secret     → totp_secret.py — el secreto vive en tabla
#     NO_ACCESS en res.users)       propia OneToOne, no en el usuario
#   auth_totp.py                  → NO portado: es `auth_totp.device`
#     (dispositivos de confianza,   (gap nombrado — ver hallazgos de la
#     hereda res.users.apikeys)     iniciativa; requiere apikeys primero)
#   auth_totp_rate_limit_log.py   → NO portado: rate-limit de intentos TOTP
#                                   (gap nombrado en el mismo hallazgo)
#   (sin contraparte)             → totp_recovery_code.py — endurecimiento
#                                   propio (0 hits de "recovery" en la ref)
from addons.authz_totp.models.totp_recovery_code import TotpRecoveryCode  # noqa: F401
from addons.authz_totp.models.totp_secret import TotpSecret  # noqa: F401
