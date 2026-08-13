# Adaptado de Odoo Community `auth_signup/models/__init__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
#
# La referencia importa 4 archivos; el mapa completo, sin omisiones:
#
#   res_partner.py         → signup_request.py (SignupRequest: el signup_type
#                            persistido, que la referencia cuelga de
#                            res.partner con _inherit) + res_partner.py (las
#                            funciones de token: generate/verify/prepare/
#                            cancel/retrieve_info sobre el partner).
#   res_users.py           → res_users.py (signup con token = set-password,
#                            reset_password, create de usuario invitado).
#   ir_http.py             → SIN archivo: inyecta la config de signup en la
#                            sesión del frontend QWeb; el SPA lee esa config
#                            por su propio endpoint.
#   res_config_settings.py → SIN archivo: toggle del scope de invitación en la
#                            UI de ajustes; aquí es el SystemParameter
#                            `authz.signup_allow_uninvited` (ya en policy.py).
from addons.authz_signup.models.signup_request import SignupRequest  # noqa: F401
from addons.authz_signup.models import res_partner  # noqa: F401
from addons.authz_signup.models import res_users  # noqa: F401
