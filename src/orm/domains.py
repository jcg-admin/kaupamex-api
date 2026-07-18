"""Dominios del ORM — fiel a ``odoo/orm/domains.py`` (Odoo 19).

En Odoo 19 la lógica de dominios (combinar leaves con ``&``/``|``/``!``) vive en
``odoo/orm/domains.py`` y ``odoo/osv/expression.py`` es un shim de compat que la
re-exporta. Aquí, con el prefijo ``odoo.`` eliminado (``orm`` ≙ ``odoo/orm``),
esta es la **definición**; ``src/osv/expression.py`` (≙ ``odoo/osv/expression.py``)
la re-exporta.

Respaldo Django: los dominios de Odoo (listas polacas ``['&', (a), (b)]``) se
combinan sobre objetos ``Q`` de Django, preservando ``AND``/``OR``/``NOT`` y las
constantes ``TRUE_DOMAIN``/``FALSE_DOMAIN``.
"""
from django.db.models import Q

__all__ = ['AND', 'OR', 'NOT', 'TRUE_DOMAIN', 'FALSE_DOMAIN']

TRUE_DOMAIN = Q()
FALSE_DOMAIN = ~Q(pk__in=[])


def AND(domains):
    """Conjunción de dominios (Odoo ``expression.AND`` / ``Domain.AND``)."""
    out = Q()
    for d in domains:
        out &= d
    return out


def OR(domains):
    """Disyunción de dominios (Odoo ``expression.OR`` / ``Domain.OR``)."""
    if not domains:
        return Q(pk__in=[])
    out = domains[0]
    for d in domains[1:]:
        out |= d
    return out


def NOT(domain):
    """Negación de un dominio (Odoo ``expression.NOT``)."""
    return ~domain
