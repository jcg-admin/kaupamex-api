"""Datos semilla del addon — equivalente nativo de ``data/*.xml``.

Adaptación de los config-params de ``auth_signup`` de Odoo
(``auth_signup.invitation_scope`` / ``auth_signup.reset_password``). Mismo
patrón que ``auth_password_policy.data``: el spec es la fuente única que
consumen la data-migration (arranque) y ``seed()`` (re-aplicación sobre el
modelo vivo, H-API-22).

Ambas banderas nacen **abiertas** ('1'), preservando el comportamiento previo
(registro y reset públicos), ahora editables en caliente (L2).
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import SystemParameter

SIGNUP_PARAMETERS = {
    'authz.signup_allow_uninvited': '1',
    'authz.signup_reset_password': '1',
}


def seed(using=DEFAULT_DB_ALIAS):
    """Crea las claves ausentes. Idempotente: nunca pisa un valor existente."""
    for key, value in SIGNUP_PARAMETERS.items():
        if not SystemParameter.objects.using(using).filter(key=key).exists():
            SystemParameter.objects.using(using).create(key=key, value=value)
