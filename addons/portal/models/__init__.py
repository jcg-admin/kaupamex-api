# Adaptado de Odoo Community `portal/models/__init__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
#
# La referencia importa 8 archivos; el mapa completo, sin omisiones:
#
#   portal_mixin.py    → portal_mixin.py (PortalMixin abstract: access_token,
#                        _portal_ensure_token, _get_share_url/get_portal_url)
#   res_partner.py     → res_partner.py (funciones frontend-writable-fields +
#                        _can_be_edited_by_current_customer + current_partner;
#                        Django no permite _inherit — son funciones sobre el
#                        partner, mismo criterio que authz_ldap.res_users)
#   ir_http.py         → SIN archivo: enruta el frontend QWeb del portal
#                        (auth='public', geoip). No aplica: el SPA es el
#                        frontend, ir_http de base ya resuelve el routing DRF.
#   ir_qweb.py         → SIN archivo: helpers de render QWeb del portal.
#   ir_ui_view.py      → SIN archivo: vistas QWeb del portal.
#   mail_message.py    → SIN archivo (198 loc): el chatter del portal (mensajes
#                        visibles al cliente por token). Gap nombrado: el
#                        chatter-por-token es una integración mail↔portal que
#                        espera su propio pase.
#   mail_thread.py     → SIN archivo (103 loc): idem, el hilo del chatter.
#   res_config_settings.py → SIN archivo: toggle en la UI de ajustes.
#   res_users_apikeys_description.py → SIN archivo: portal.allow_api_keys —
#                        este árbol autentica por sesión (ADR-018), sin API
#                        keys que gobernar.
#
# El `_document_check_access` (corazón de la compartición por token) vive en
# el controller de la referencia (portal.py:961-980); aquí en ../services.py.
from addons.portal.models import portal_mixin  # noqa: F401
from addons.portal.models import res_partner  # noqa: F401
