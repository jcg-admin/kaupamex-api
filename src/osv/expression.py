"""``expression`` — combinadores de dominios, fiel a ``odoo/osv/expression.py``.

Los dominios de Odoo (listas polacas ``['&', (a), (b)]``) se combinan aquí sobre
objetos ``Q`` de Django, preservando los nombres ``AND``/``OR``/``NOT`` y las
constantes ``TRUE_DOMAIN``/``FALSE_DOMAIN``. Un addon escribe
``from osv import expression`` y usa ``expression.AND([q1, q2])``.
"""
from django.db.models import Q

TRUE_DOMAIN = Q()
FALSE_DOMAIN = ~Q(pk__in=[])


def AND(domains):
    """Conjunción de dominios (Odoo ``expression.AND``)."""
    out = Q()
    for d in domains:
        out &= d
    return out


def OR(domains):
    """Disyunción de dominios (Odoo ``expression.OR``)."""
    if not domains:
        return Q(pk__in=[])
    out = domains[0]
    for d in domains[1:]:
        out |= d
    return out


def NOT(domain):
    """Negación de un dominio (Odoo ``expression.NOT``)."""
    return ~domain
