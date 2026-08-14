"""Facade de compatibilidad de ``addons.authz`` (SOL-094 frente B).

La lógica que antes vivía monolítica aquí (~388 LOC, ≥5 responsabilidades) se
partió en módulos cohesivos —un concern por archivo, al estilo Odoo
(``ir.model.access`` / ``ir.rule`` / ``res.groups`` separados):

- :mod:`addons.authz.resolution` — resolver de capacidades (L2) + checks.
- :mod:`addons.authz.catalog` — catálogo ``Capability`` + códigos sensibles.
- :mod:`addons.authz_audit.audit` — ``AuthzEvent`` (DEC-07), app opcional.
- :mod:`addons.authz_reauth.reauth` — re-autenticación de acciones sensibles
  (DEC-12), app opcional (análoga a ``auth_totp`` de Odoo).
- :mod:`addons.authz.bootstrap` — asignación idempotente de roles base.

Este módulo re-exporta los nombres públicos para **no romper** a los
consumidores existentes (``from addons.authz.services import X``). Los
consumidores se migran a los módulos concretos en un follow-up documentado
(H-API-RR-06); cuando el último deje de importar de aquí, este facade se
elimina.
"""
from addons.authz_audit.audit import (  # noqa: F401
    _client_ip,
    _session_key,
    audit_authz_event,
)
from addons.authz.bootstrap import assign_buyer_role  # noqa: F401
from addons.authz.catalog import (  # noqa: F401
    _CRUD_VERBS,
    _SENSITIVE_CACHE_KEY,
    all_capability_codes,
    code_requires_fresh_session,
    invalidate_sensitive_codes,
    sensitive_codes,
    unknown_capability_codes,
)
from addons.authz_reauth.reauth import (  # noqa: F401
    REAUTH_CAP_CODE,
    _reauth_ttl,
    assert_session_fresh,
    close_reauth_session,
    has_active_reauth_session,
    open_reauth_session,
)
from addons.authz.resolution import (  # noqa: F401
    BUYER_ROLE_CODE,
    SUPERADMIN_ROLE_CODE,
    _CACHE_TTL,
    _NO_BYPASS_PREFIXES,
    _cache_key,
    _split_graded_named,
    _unexpired_q,
    has_capability,
    has_level,
    invalidate_capabilities,
    is_superadmin,
    resolve_capabilities,
    resolve_capability_levels,
)
