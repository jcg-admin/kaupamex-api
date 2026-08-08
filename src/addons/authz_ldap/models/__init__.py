# Adaptado de Odoo Community `auth_ldap/models/__init__.py` (LGPL-3) —
# atribución y aviso de licencia preservados (DEC-KX-03).
#
# La referencia importa 4 archivos; aquí el mapa completo, sin omisiones:
#
#   res_company_ldap.py  → res_company_ldap.py (LDAPWrapper + CompanyLdap)
#   res_users.py         → res_users.py (change_password / set_empty_password;
#                          _login/_check_credentials viven en backends.py
#                          (mismo paquete models/) porque
#                          AUTHENTICATION_BACKENDS es la cadena de
#                          super()._login en Django)
#   res_company.py       → SIN archivo: su único contenido es la One2many
#                          `ldaps`, que en Django ES el reverso de la FK
#                          (related_name='ldaps' en CompanyLdap.company).
#                          Crear el archivo sería fabricar un stub vacío.
#   res_config_settings.py → SIN archivo: expone la o2m en la UI de ajustes
#                          de `base_setup`, que este árbol no tiene; la
#                          superficie de configuración es el CRUD DRF
#                          (../views.py).
from addons.authz_ldap.models.res_company_ldap import (  # noqa: F401
    LDAP_AVAILABLE,
    LDAPWrapper,
    CompanyLdap,
)
from addons.authz_ldap.models import res_users  # noqa: F401
