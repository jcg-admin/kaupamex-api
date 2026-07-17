"""Bootstrap de roles — addons.authz.

Un concern por módulo (SOL-094 frente B): asignación idempotente de roles base
al ciclo de vida del usuario (registro, backfill). Antes vivía mezclado en
``services.py``.
"""
from addons.authz.models import Role, RoleAssignment
from addons.authz.resolution import BUYER_ROLE_CODE, invalidate_capabilities


def assign_buyer_role(user):
    """Asigna el rol ``comprador`` a ``user`` (idempotente).

    Gobierna el menú de cuenta dinámico (``account.*``). Se llama al registrarse
    y desde el backfill. **Tolerante:** si el rol no está sembrado (tests sin
    ``seed_authz``) no hace nada — así no rompe los flujos que crean usuarios
    sin el catálogo authz. Devuelve True si quedó asignado."""
    if getattr(user, 'pk', None) is None:
        return False
    role = Role.objects.filter(code=BUYER_ROLE_CODE).first()
    if role is None:
        return False
    _, created = RoleAssignment.objects.get_or_create(user=user, role=role)
    if created:
        invalidate_capabilities(user.pk)
    return True
