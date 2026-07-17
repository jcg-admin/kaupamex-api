"""Resolver de capacidades — addons.authz (Opción B, DEC-AUTHZ-01).

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
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from addons.authz.exceptions import ReauthRequired
from addons.authz.models import (
    AccessLevel,
    AuthzEvent,
    Capability,
    DirectEntitlement,
    EntitlementRevocation,
    ReauthSession,
    Role,
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


# ─── DEC-12 — re-autenticación para acciones sensibles ───────────────────────
# Verbos CRUD graduados (DEC-11). Si el ``code`` requerido termina en uno de
# estos, es un sustantivo graduado (``noun.verbo``); si no, es una acción
# nombrada cuyo propio ``code`` es la capacidad (``platform.provision``).
_CRUD_VERBS = frozenset({'view', 'create', 'edit', 'full'})
_SENSITIVE_CACHE_KEY = 'authz:sensitive_codes'
# Código de auditoría de la re-autenticación (no es una Capability gateada; es la
# etiqueta del AuthzEvent de apertura/cierre). Deliberadamente NO "sudo".
REAUTH_CAP_CODE = 'authz.reauth'


def _reauth_ttl():
    """Segundos de vida de una sesión reautenticada (``AUTHZ_REAUTH_TTL``,
    default 15 min)."""
    return int(getattr(settings, 'AUTHZ_REAUTH_TTL', 900))


def sensitive_codes():
    """Set de ``Capability.code`` marcados ``is_sensitive`` (cacheado).

    Incluye tanto los sustantivos graduados sensibles (``payments``, ``settings``,
    …) como las acciones nombradas sensibles (``platform.provision``, …). Se
    invalida con ``invalidate_sensitive_codes`` tras re-sembrar el catálogo."""
    cached = cache.get(_SENSITIVE_CACHE_KEY)
    if cached is not None:
        return cached
    codes = set(
        Capability.objects
        .filter(is_sensitive=True, is_active=True)
        .values_list('code', flat=True)
    )
    cache.set(_SENSITIVE_CACHE_KEY, codes, _CACHE_TTL)
    return codes


def invalidate_sensitive_codes():
    """Purga la cache de códigos sensibles (llamar tras re-sembrar el catálogo)."""
    cache.delete(_SENSITIVE_CACHE_KEY)


def code_requires_fresh_session(code, unsafe_method):
    """True si ejercer ``code`` con este método exige una sesión elevada (DEC-12).

    - Sustantivo graduado (``noun.verbo`` con verbo CRUD): exige frescura sii el
      **sustantivo** es sensible **y** el método es **mutante** (``unsafe_method``).
      Leer datos sensibles (``payments.view``) NO exige re-auth — la capacidad ya
      lo gatea; el re-auth protege la mutación peligrosa.
    - Acción nombrada (``platform.provision``, ``inventory.adjust``): exige
      frescura sii el propio ``code`` es sensible (son intrínsecamente mutantes)."""
    if not code:
        return False
    sset = sensitive_codes()
    noun, sep, verb = code.rpartition('.')
    if sep and verb in _CRUD_VERBS:
        return noun in sset and unsafe_method
    return code in sset


def all_capability_codes():
    """Set de ``Capability.code`` activos sembrados (para validar declaraciones)."""
    return set(
        Capability.objects.filter(is_active=True).values_list('code', flat=True)
    )


def unknown_capability_codes(declared_codes):
    """Códigos declarados en vistas que NO mapean a un ``Capability`` sembrado.

    Adopta la idea de ``assert_valid_permission`` de pretix en data-driven
    (analisis-mapeo-registro-permisos-pretix-vs-catalogo-db, azúcar #5): un typo
    en ``required_capability``/``permission_map`` produce un *fail-closed*
    silencioso (403 perpetuo) que este check destapa ruidosamente.

    Reglas de resolución (mismas que ``resolve_capabilities``): un graded
    ``noun.verbo`` (verbo CRUD) valida contra el ``noun``; una acción nombrada
    (``platform.provision``, ``account.profile``) valida contra el code exacto.
    Devuelve el set de códigos desconocidos (vacío = todo válido)."""
    seeded = all_capability_codes()
    unknown = set()
    for code in declared_codes:
        if not code:
            continue
        noun, sep, verb = code.rpartition('.')
        if sep and verb in _CRUD_VERBS:
            if noun not in seeded:
                unknown.add(code)
        elif code not in seeded:
            unknown.add(code)
    return unknown


def _client_ip(request):
    xff = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    return xff or request.META.get('REMOTE_ADDR') or None


def _session_key(request):
    return getattr(getattr(request, 'session', None), 'session_key', '') or ''


def audit_authz_event(request, action, code, extra=None):
    """Registra un ``AuthzEvent`` (DEC-07) PII-safe. No bloqueante: un fallo del
    audit jamás rompe la request original (mismo criterio DEC-LOG-04)."""
    try:
        actor = getattr(request, 'user', None)
        if not getattr(actor, 'is_authenticated', False):
            actor = None
        AuthzEvent.objects.create(
            actor=actor,
            action=action,
            capability_code=code or '',
            ip_addr=_client_ip(request),
            correlation_id=getattr(request, 'correlation_id', '') or '',
            extra_json=extra,
        )
    except Exception:
        # silent OK because DEC-LOG-04: sellar la auditoría nunca debe romper el
        # flujo de autorización ni la respuesta al cliente.
        pass


def has_active_reauth_session(user, session_key):
    """True si ``user`` tiene una sesión reautenticada vigente para
    ``session_key``."""
    if not getattr(user, 'is_authenticated', False) or user.pk is None:
        return False
    return ReauthSession.objects.filter(
        user_id=user.pk, session_key=session_key or '',
        expires_at__gt=timezone.now(),
    ).exists()


def open_reauth_session(user, session_key, ip_addr=None):
    """Abre (o refresca) la sesión reautenticada de ``user`` para ``session_key``.

    Una fila por ``(user, session_key)``: reabrir renueva ``started_at`` y
    ``expires_at``. Devuelve la fila."""
    now = timezone.now()
    obj, _ = ReauthSession.objects.update_or_create(
        user_id=user.pk, session_key=session_key or '',
        defaults={
            'started_at': now,
            'expires_at': now + timedelta(seconds=_reauth_ttl()),
            'ip_addr': ip_addr,
        },
    )
    return obj


def close_reauth_session(user, session_key):
    """Cierra la sesión reautenticada de ``user`` para ``session_key``."""
    ReauthSession.objects.filter(
        user_id=user.pk, session_key=session_key or '',
    ).delete()


def assert_session_fresh(request, code, unsafe_method):
    """Gate DEC-12: si ejercer ``code`` exige re-autenticación y no hay una sesión
    reautenticada fresca, audita el ``DENY`` y lanza ``ReauthRequired`` (403
    ``REAUTH_REQUIRED``).

    Invocado desde ``HasCapability.has_permission`` **después** de confirmar la
    capacidad — data-driven, sin cablear vista por vista. El **superadmin NO está
    exento**: es la cuenta más privilegiada la que DEC-12 quiere proteger."""
    if not code_requires_fresh_session(code, unsafe_method):
        return
    if has_active_reauth_session(request.user, _session_key(request)):
        return
    audit_authz_event(
        request, AuthzEvent.ACTION_DENY, code, {'reason': 'reauth_required'},
    )
    raise ReauthRequired(window_seconds=_reauth_ttl())


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
