"""Catálogo de capacidades y códigos sensibles — addons.authz.

Un concern por módulo (SOL-094 frente B): consulta del catálogo ``Capability``
(códigos sembrados, sensibles) y la clasificación graded-vs-named usada para
validar declaraciones y decidir frescura de sesión (DEC-12). Antes vivía
mezclado en ``services.py``.
"""
from django.core.cache import cache

from addons.authz.models import Capability
from addons.authz.resolution import _CACHE_TTL

# ─── DEC-12 — clasificación graded vs named ──────────────────────────────────
# Verbos CRUD graduados (DEC-11). Si el ``code`` requerido termina en uno de
# estos, es un sustantivo graduado (``noun.verbo``); si no, es una acción
# nombrada cuyo propio ``code`` es la capacidad (``platform.provision``).
_CRUD_VERBS = frozenset({'view', 'create', 'edit', 'full'})
_SENSITIVE_CACHE_KEY = 'authz:sensitive_codes'


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
