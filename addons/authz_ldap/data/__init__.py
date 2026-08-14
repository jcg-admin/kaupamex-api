"""Datos semilla del addon — equivalente nativo de ``data/*.xml``.

Config-param L2 del comportamiento de referrals LDAP. En la referencia es el
``ir.config_parameter`` ``auth_ldap.disable_chase_ref`` leído con default
``'True'`` (``res_company_ldap.py:109``); aquí nace sembrado con ese mismo
default y queda editable en caliente.

Spec único que consumen la data-migration de arranque y ``seed()``
(re-aplicación sobre el modelo vivo, patrón H-API-22 de ``authz_totp``).
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import SystemParameter

LDAP_PARAMETERS = {
    'authz_ldap.disable_chase_ref': 'True',
}


def seed(using=DEFAULT_DB_ALIAS):
    """Crea las claves ausentes. Idempotente: nunca pisa un valor existente."""
    for key, value in LDAP_PARAMETERS.items():
        if not SystemParameter.objects.using(using).filter(key=key).exists():
            SystemParameter.objects.using(using).create(key=key, value=value)
