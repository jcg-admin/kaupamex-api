# Adaptado de Odoo Community `auth_oauth/models/__init__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
#
# La referencia importa 4 archivos; el mapa completo, sin omisiones:
#
#   auth_oauth.py            → oauth_provider.py (OauthProvider — el modelo
#                              `auth.oauth.provider` de configuración)
#   res_users.py             → res_users.py (OauthAccount con los campos que
#                              la referencia cuelga de res.users + las
#                              funciones _auth_oauth_*; el fallback de
#                              _check_credentials vive en ../backends.py)
#   ir_config_parameter.py   → SIN archivo: su único contenido fija el
#                              client_id del proveedor Odoo.com al
#                              database.uuid en el init forzado — es la
#                              integración de cuentas de la casa Odoo, sin
#                              análogo aquí.
#   res_config_settings.py   → PENDIENTE, no divergencia. Decía "la UI de
#                              ajustes de `base_setup`, que este árbol no
#                              tiene"; medido 2026-08-27 es FALSO: existe, y
#                              once addons extienden `ResConfigSettings`. La
#                              premisa caducó al portarse `base_setup`, sin que
#                              este archivo cambiara. Ver tarea #84.
from addons.authz_oauth.models.oauth_provider import OauthProvider  # noqa: F401
from addons.authz_oauth.models.res_users import OauthAccount  # noqa: F401
