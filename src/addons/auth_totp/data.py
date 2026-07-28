"""Datos semilla del addon — equivalente nativo de ``data/*.xml``.

Config-params L2 del segundo factor: el emisor que se muestra en la app
autenticadora y cuántos códigos de recuperación se generan. Ambos nacen con el
comportamiento previo cableado y quedan editables en caliente.

Spec único que consumen las data-migrations ``0001_initial`` /
``0002_totprecoverycode`` (arranque) y ``seed()`` (re-aplicación sobre el modelo
vivo, H-API-22).
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import SystemParameter

TOTP_PARAMETERS = {
    'authz.totp_issuer': 'Kaupamex',        # operador L0 de la plataforma
    'authz.totp_recovery_codes': '10',
}


def seed(using=DEFAULT_DB_ALIAS):
    """Crea las claves ausentes. Idempotente: nunca pisa un valor existente."""
    for key, value in TOTP_PARAMETERS.items():
        if not SystemParameter.objects.using(using).filter(key=key).exists():
            SystemParameter.objects.using(using).create(key=key, value=value)
