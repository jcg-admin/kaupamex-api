"""Resolver de capacidades — apps.authz (Opción B, DEC-AUTHZ-01).

Reemplaza ``user.get_all_permissions()`` del RBAC nativo de Django (que ya no
existe: ``IdentityUser`` es U-D puro, sin ``PermissionsMixin``). La autorización
efectiva de un usuario es:

    capacidades = (roles asignados → sus capacidades)
                ∪ (grants directos: DirectEntitlement)
                − (revocaciones: EntitlementRevocation)

El **superadmin** (rol ``superadmin``, DEC-01=B) NO se materializa como set de
todas las capacidades: se cortocircuita en ``has_capability`` (bypass), salvo el
dominio ``pos.*`` que exige capacidad explícita incluso al superadmin
(segregación de caja, DEC-06).

Diseño ratificado en :ref:`analisis-enforcement-hascapability-isowner`.
"""
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from apps.authz.models import DirectEntitlement, EntitlementRevocation, RoleAssignment

SUPERADMIN_ROLE_CODE = 'superadmin'
# Dominios que exigen capacidad explícita incluso al superadmin (DEC-06).
_NO_BYPASS_PREFIXES = ('pos.',)
_CACHE_TTL = 300  # segundos (sin Redis; usa el backend de cache configurado)


def _cache_key(user_id):
    return f'authz:caps:{user_id}'


def is_superadmin(user):
    """True si el usuario tiene el rol ``superadmin`` vigente (no expirado)."""
    if not getattr(user, 'is_authenticated', False) or user.pk is None:
        return False
    now = timezone.now()
    return RoleAssignment.objects.filter(
        user_id=user.pk, role__code=SUPERADMIN_ROLE_CODE,
    ).filter(_unexpired_q(now)).exists()


def _unexpired_q(now):
    return Q(expires_at__isnull=True) | Q(expires_at__gt=now)


def resolve_capabilities(user):
    """Set de códigos ``'dominio.verbo'`` que el usuario posee (sin el bypass de
    superadmin — ese se aplica en ``has_capability``). Cacheado ``_CACHE_TTL``s."""
    if not getattr(user, 'is_authenticated', False) or user.pk is None:
        return set()

    key = _cache_key(user.pk)
    cached = cache.get(key)
    if cached is not None:
        return cached

    now = timezone.now()
    unexpired = _unexpired_q(now)

    role_caps = set(
        RoleAssignment.objects
        .filter(user_id=user.pk).filter(unexpired)
        .values_list('role__capabilities__code', flat=True)
    )
    role_caps.discard(None)

    direct = set(
        DirectEntitlement.objects
        .filter(user_id=user.pk)
        .values_list('capability__code', flat=True)
    )
    revoked = set(
        EntitlementRevocation.objects
        .filter(user_id=user.pk)
        .values_list('capability__code', flat=True)
    )

    caps = (role_caps | direct) - revoked
    cache.set(key, caps, _CACHE_TTL)
    return caps


def has_capability(user, code):
    """True si el usuario puede ejercer ``code``. Superadmin hace bypass salvo
    los dominios de ``_NO_BYPASS_PREFIXES`` (POS)."""
    if not code:
        return False
    if is_superadmin(user) and not code.startswith(_NO_BYPASS_PREFIXES):
        return True
    return code in resolve_capabilities(user)


def invalidate_capabilities(user_id):
    """Purga la cache de capacidades de un usuario (llamar tras mutar sus
    roles/grants)."""
    cache.delete(_cache_key(user_id))
