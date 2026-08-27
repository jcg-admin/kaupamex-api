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
#   auth_totp_device.py     → signals.py — sus DOS símbolos (`unlink` que
#                             avisa, `_classify_by_user` que agrupa) portados
#                             como `pre_delete` sobre `AuthTotpDevice` +
#                             `on_commit`.
#                             CORREGIDO 2026-08-27: esta línea decía "modelo
#                             NO portado (gap nombrado en H-API-232)" y era
#                             FALSO — `AuthTotpDevice` vive en
#                             `addons/authz_totp/models/auth_totp.py:121`. La
#                             nota fue cierta al escribirse y caducó cuando el
#                             addon hermano portó el modelo, sin que ningún
#                             archivo de éste cambiara (≙ H-API-823/827).
#   res_config_settings.py  → PENDIENTE, no divergencia. La nota decía que
#                             expone la política "en la UI de ajustes de
#                             `base_setup`"; medido 2026-08-27, `base_setup`
#                             SÍ existe con su `models/res_config_settings.py`.
#                             Lo que sí es cierto es la otra mitad: la política
#                             vive aquí en el SystemParameter
#                             `authz_totp.policy` (`PARAM_TOTP_POLICY`), que es
#                             el mismo dato que el `config_parameter=` del
#                             campo de la referencia. Qué superficie la expone
#                             —`ResConfigSettings` o el CRUD DRF— es la
#                             decisión #84; hasta entonces el archivo no se
#                             escribe.
#
# Este addon no declara modelos propios (igual que la referencia: solo
# _inherit) — sus semillas son plantillas de correo + config-params.
from addons.authz_totp_mail.models import res_users  # noqa: F401
