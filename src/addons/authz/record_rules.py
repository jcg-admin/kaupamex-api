"""Motor de record rules nativo (L3) — aplicación de ``AccessRule`` (DEC-KX-02).

Adaptado de ``odoo/addons/base/models/ir_rule.py`` (Odoo Community, LGPL-3) —
referencia de patrón/comportamiento, reimplementación nativa (SOL-094).

Dada una consulta, un usuario y una **operación** (``read``/``write``/
``create``/``unlink``), compone los dominios de las ``AccessRule`` activas que
conceden esa operación y las aplica al queryset. **Aditivo**: refina las filas
visibles dentro de la company ya resuelta por L1; no reemplaza el aislamiento
por company (``CompanyScopedManager``).

Semántica ``ir.rule`` (``ir_rule.py:_compute_domain``):

- Se filtran las reglas por ``perm_<mode>`` (la operación pedida).
- Las reglas **de rol** del usuario se combinan con **OR** (basta que una
  regla de algún rol conceda la fila).
- Las reglas **globales** (``role`` nulo — ``_compute_global = not groups``) se
  combinan con **AND** (obligatorias) y se cruzan con el OR de las de rol.
- Sin reglas para el modelo → sin restricción (el fail-closed lo aporta L1).
"""
from django.db.models import Q

from addons.authz.models import AccessRule, RoleAssignment

# Placeholders resueltos en runtime contra el usuario de la request.
_PLACEHOLDERS = {
    '$user': lambda user: getattr(user, 'pk', None),
    '$company': lambda user: getattr(user, 'company_id', None),
}


def _resolve_value(value, user):
    """Sustituye un placeholder (``$user``/``$company``) por su valor real."""
    if isinstance(value, str) and value in _PLACEHOLDERS:
        return _PLACEHOLDERS[value](user)
    return value


def _domain_to_q(domain, user):
    """Convierte un dominio (dict de filtros ORM) en un ``Q``, resolviendo placeholders.

    Un dominio vacío (``{}``) produce ``Q()`` — regla universal, sin restricción
    (paridad ``Domain.TRUE`` de ``ir.rule`` cuando no hay ``domain_force``).
    """
    return Q(**{key: _resolve_value(val, user) for key, val in domain.items()})


def access_q_for(model_label, user, mode='read'):
    """``Q`` combinada de las ``AccessRule`` del usuario para ``model_label`` y ``mode``.

    Devuelve ``None`` cuando el usuario no está autenticado o no hay reglas
    (globales ni de rol) que concedan ``mode`` sobre el modelo — en cuyo caso el
    queryset queda **sin restricción** (L3 es aditivo, refina L1/L2). Compone
    con la semántica ``ir.rule``: reglas globales AND, reglas de rol OR.
    """
    if mode not in AccessRule.MODES:
        raise ValueError(f'Invalid mode: {mode!r}')
    if not getattr(user, 'is_authenticated', False) or getattr(user, 'pk', None) is None:
        return None
    role_ids = list(
        RoleAssignment.objects.filter(user_id=user.pk).values_list('role_id', flat=True)
    )
    # Reglas activas del modelo que conceden la operación pedida, restringidas a
    # las globales (role nulo) o las de los roles del usuario.
    rules = AccessRule.objects.filter(
        is_active=True, model_label=model_label.lower(), **{f'perm_{mode}': True},
    ).filter(Q(role__isnull=True) | Q(role_id__in=role_ids))

    global_domains = []
    group_domains = []
    for rule in rules:
        sub = _domain_to_q(rule.domain, user)
        if rule.role_id is None:
            global_domains.append(sub)
        else:
            group_domains.append(sub)

    if not global_domains and not group_domains:
        return None

    # Globales con AND; de rol con OR; luego el OR se cruza (AND) con las globales.
    combined = None
    for dom in global_domains:
        combined = dom if combined is None else (combined & dom)
    if group_domains:
        group_or = None
        for dom in group_domains:
            group_or = dom if group_or is None else (group_or | dom)
        combined = group_or if combined is None else (combined & group_or)
    return combined


def apply_access_rules(queryset, user, mode='read'):
    """Aplica las ``AccessRule`` (L3) del usuario al ``queryset`` para ``mode``.

    Sin reglas para el modelo del queryset → se devuelve intacto. Con reglas →
    se filtra por la ``Q`` combinada (global AND / rol OR).
    """
    combined = access_q_for(queryset.model._meta.label_lower, user, mode=mode)
    return queryset if combined is None else queryset.filter(combined)
