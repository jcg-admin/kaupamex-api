# Adaptado de Odoo Community `auth_totp_mail/models/__init__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
#
# La referencia importa 3 archivos; el mapa completo, sin omisiones:
#
#   res_users.py            → res_users.py (clave/código/envío/verificación
#                             del 2FA por correo, política, invitación). El
#                             write-hook de notificación al activar/desactivar
#                             2FA vive en signals.py (mismo paquete models/;
#                             Django signals sobre TotpSecret — no hay
#                             _inherit). Se registra en apps.py::ready() vía
#                             importlib, no se importa aquí (AppRegistryNotReady).
#   auth_totp_device.py     → SIN archivo: extiende `auth_totp.device`
#                             (dispositivos de confianza), modelo NO portado
#                             (gap nombrado en H-API-232).
#   res_config_settings.py  → SIN archivo: expone la política en la UI de
#                             ajustes de `base_setup`; aquí la política es el
#                             SystemParameter `authz_totp.policy`.
#
# Este addon no declara modelos propios (igual que la referencia: solo
# _inherit) — sus semillas son plantillas de correo + config-params.
from addons.authz_totp_mail.models import res_users  # noqa: F401
