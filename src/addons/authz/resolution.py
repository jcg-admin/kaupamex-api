"""Resolver de capacidades (L2) — addons.authz (Opción B, DEC-AUTHZ-01).

Un concern por módulo, al estilo Odoo (donde ``ir.model.access`` / ``ir.rule`` /
``res.groups`` viven en archivos separados). Este módulo resuelve el set de
capacidades efectivas de un usuario y expone los checks ``has_capability`` /
``has_level``. Antes vivía mezclado en ``services.py`` (SRP, SOL-094 frente B).

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

from addons.authz.models import (
    AccessLevel,
    DirectEntitlement,
    EntitlementRevocation,
    RoleAssignment,
    RoleCapability,
)

SUPERADMIN_ROLE_CODE = 'superadmin'
# Rol base del comprador (DEC-AUTHZ-BUYER): agrupa las capacidades ``account.*``
# que gobiernan el menú de cuenta dinámico. Se asigna al registrarse y con el
# backfill de compradores existentes.
BUYER_ROLE_CODE = 'comprador'
# Dominios que exigen capacidad explícita incluso al superadmin (DEC-06).
_NO_BYPASS_PREFIXES = ('pos.',)
_CACHE_TTL = 300  # segundos (sin Redis; usa el backend de cache configurado)


def _cache_key(user_id):
    return f'authz:caps:{user_id}'


def _unexpired_q(now):
    return Q(expires_at__isnull=True) | Q(expires_at__gt=now)


def is_superadmin(user):
    """True si el usuario tiene el rol ``superadmin`` vigente (no expirado)."""
    if not getattr(user, 'is_authenticated', False) or user.pk is None:
        return False
    now = timezone.now()
    return RoleAssignment.objects.filter(
        user_id=user.pk, role__code=SUPERADMIN_ROLE_CODE,
    ).filter(_unexpired_q(now)).exists()


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
    role_ids = list(
        RoleAssignment.objects
        .filter(user_id=user.pk).filter(_unexpired_q(now))
        .values_list('role_id', flat=True)
    )

    # Gate L1-a (DEC-T7 / SOL-085): filtra las capacidades L2 por los módulos
    # con suscripción activa de la Company del usuario. ``company=None`` (operador
    # L0 cross-company o usuario sin asignar) → sin gate. Se aplica al origen de
    # las capacidades (roles + directas); las revocaciones nunca se filtran.
    company = getattr(user, 'company', None)
    active_modules = None if company is None else company.active_module_codes(now)

    role_cap_qs = RoleCapability.objects.filter(role_id__in=role_ids)
    direct_qs = DirectEntitlement.objects.filter(user_id=user.pk)
    if active_modules is not None:
        role_cap_qs = role_cap_qs.filter(capability__module__code__in=active_modules)
        direct_qs = direct_qs.filter(capability__module__code__in=active_modules)

    # Graded nouns (code sin punto) → nivel máximo entre roles; acciones
    # nombradas (code con punto, no verbo CRUD) → membresía directa (DEC-11).
    graded, named = _split_graded_named(
        role_cap_qs.values_list('capability__code', 'level')
    )

    role_caps = set(named)
    for noun, level in graded.items():
        for verb in AccessLevel(level).implied_verbs():
            role_caps.add(f'{noun}.{verb}')

    direct = set(
        direct_qs.values_list('capability__code', flat=True)
    )
    revoked = set(
        EntitlementRevocation.objects
        .filter(user_id=user.pk)
        .values_list('capability__code', flat=True)
    )

    caps = (role_caps | direct) - revoked
    cache.set(key, caps, _CACHE_TTL)
    return caps


def _split_graded_named(code_level_pairs):
    """Parte ``(code, level)`` en ``({noun: max_level}, {named_action_code})``.

    ``code`` sin punto → noun graduado; con punto → acción nombrada (membresía).
    """
    graded = {}
    named = set()
    for code, level in code_level_pairs:
        if code is None:
            continue
        if '.' in code:
            named.add(code)
        else:
            graded[code] = max(graded.get(code, AccessLevel.NONE), level)
    return graded, named


def resolve_capability_levels(user):
    """``{noun: AccessLevel}`` que el usuario posee vía roles (nivel máximo).

    Solo capacidades graduadas (noun sin punto). Las acciones nombradas no
    tienen nivel — se consultan con ``has_capability`` por membresía.
    """
    if not getattr(user, 'is_authenticated', False) or user.pk is None:
        return {}
    now = timezone.now()
    role_ids = list(
        RoleAssignment.objects
        .filter(user_id=user.pk).filter(_unexpired_q(now))
        .values_list('role_id', flat=True)
    )
    graded, _ = _split_graded_named(
        RoleCapability.objects
        .filter(role_id__in=role_ids)
        .values_list('capability__code', 'level')
    )
    return {noun: AccessLevel(level) for noun, level in graded.items()}


def has_capability(user, code):
    """True si el usuario puede ejercer ``code``. Superadmin hace bypass salvo
    los dominios de ``_NO_BYPASS_PREFIXES`` (POS)."""
    if not code:
        return False
    if is_superadmin(user) and not code.startswith(_NO_BYPASS_PREFIXES):
        return True
    return code in resolve_capabilities(user)


def has_level(user, noun, min_level):
    """True si el usuario posee el sustantivo graduado ``noun`` a nivel
    ≥ ``min_level`` (DEC-11).

    ``noun`` es un sustantivo sin punto (``catalogue``, ``orders``, …) y
    ``min_level`` un ``AccessLevel``. El superadmin hace bypass —salvo los
    dominios de ``_NO_BYPASS_PREFIXES`` (POS), que exigen capacidad explícita
    incluso al superadmin (DEC-06). Solo aplica a capacidades graduadas; las
    acciones nombradas (con punto) se consultan con ``has_capability``."""
    if not noun:
        return False
    if is_superadmin(user) and not f'{noun}.'.startswith(_NO_BYPASS_PREFIXES):
        return True
    return resolve_capability_levels(user).get(noun, AccessLevel.NONE) >= min_level


def invalidate_capabilities(user_id):
    """Purga la cache de capacidades de un usuario (llamar tras mutar sus
    roles/grants)."""
    cache.delete(_cache_key(user_id))
