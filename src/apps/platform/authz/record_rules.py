"""Motor de record rules nativo (L3) — aplicación de ``AccessRule`` (DEC-KX-02).

Reimplementación nativa del ``ir.rule`` de Odoo: dada una consulta y un usuario,
compone los dominios de las ``AccessRule`` activas de los roles del usuario y las
aplica al queryset. **Aditivo**: refina las filas visibles dentro de la company
ya resuelta por L1; no reemplaza el aislamiento por company
(``CompanyScopedManager``). Reglas de distintos roles se combinan con **OR**
(semántica de grupos de ``ir.rule``). Sin reglas → sin restricción.
"""
from django.db.models import Q

from apps.platform.authz.models import AccessRule, RoleAssignment

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
    """Convierte un dominio (dict de filtros ORM) en un ``Q``, resolviendo placeholders."""
    return Q(**{key: _resolve_value(val, user) for key, val in domain.items()})


def access_q_for(model_label, user):
    """``Q`` combinada de las ``AccessRule`` activas del usuario para ``model_label``.

    Devuelve ``None`` cuando el usuario no está autenticado, no tiene roles, o no
    hay reglas para el modelo — en cuyo caso el queryset queda **sin restricción**
    (L3 es aditivo, refina L1/L2). Las reglas de distintos roles se combinan con
    OR: una fila es visible si **alguna** regla de **algún** rol del usuario la
    concede.
    """
    if not getattr(user, 'is_authenticated', False) or getattr(user, 'pk', None) is None:
        return None
    role_ids = list(
        RoleAssignment.objects.filter(user_id=user.pk).values_list('role_id', flat=True)
    )
    if not role_ids:
        return None
    rules = AccessRule.objects.filter(
        is_active=True, model_label=model_label.lower(), role_id__in=role_ids,
    )
    combined = None
    for rule in rules:
        sub = _domain_to_q(rule.domain, user)
        combined = sub if combined is None else (combined | sub)
    return combined


def apply_access_rules(queryset, user):
    """Aplica las ``AccessRule`` (L3) del usuario al ``queryset``.

    Sin reglas para el modelo del queryset → se devuelve intacto. Con reglas →
    se filtra por la ``Q`` combinada (OR entre roles).
    """
    combined = access_q_for(queryset.model._meta.label_lower, user)
    return queryset if combined is None else queryset.filter(combined)
