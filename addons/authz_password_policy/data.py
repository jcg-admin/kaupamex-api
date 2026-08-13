"""Datos semilla del addon — equivalente nativo de ``data/defaults.xml``.

En Odoo los defaults del módulo viven en ``data/*.xml`` y se re-aplican en cada
*install/update* del addon. Aquí el spec vive en este módulo y lo consumen dos
lados, igual que ``base._DEFAULT_PARAMETERS`` (``base/0002``):

- la **data-migration** ``0001_seed_password_minlength`` (arranque de la BD), que
  lo aplica sobre el modelo histórico;
- **``seed()``** (abajo), para re-aplicarlo sobre el modelo vivo cuando la fila
  desaparece sin que la migración vuelva a correr — el caso de H-API-22.

El valor por defecto (8) preserva el comportamiento previo del
``MinimumLengthValidator`` de Django, ahora editable en caliente (L2).
"""
from django.db import DEFAULT_DB_ALIAS

from addons.base.models import SystemParameter

PASSWORD_POLICY_PARAMETERS = {
    'authz.password_minlength': '8',
}


def seed(using=DEFAULT_DB_ALIAS):
    """Crea las claves ausentes. Idempotente: nunca pisa un valor existente."""
    for key, value in PASSWORD_POLICY_PARAMETERS.items():
        if not SystemParameter.objects.using(using).filter(key=key).exists():
            SystemParameter.objects.using(using).create(key=key, value=value)
