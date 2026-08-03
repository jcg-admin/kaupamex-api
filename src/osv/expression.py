"""``expression`` — fiel a ``odoo/osv/expression.py`` (Odoo 19).

En Odoo 19 la lógica de dominios se movió a ``odoo/orm/domains.py`` y
``odoo/osv/expression.py`` quedó como shim de compat que la re-exporta. Aquí se
replica: la definición vive en ``orm/domains.py`` (≙ ``odoo/orm/domains.py``) y
este módulo la re-exporta bajo ``expression`` para que un addon escriba
``from osv import expression`` y use ``expression.AND([q1, q2])`` leyendo como su
fuente Odoo (``from odoo.osv import expression``).
"""
from orm.domains import (            # noqa: F401  (re-export de orm/domains)
    AND,
    FALSE_DOMAIN,
    NOT,
    OR,
    TRUE_DOMAIN,
    to_q,
)

__all__ = ['AND', 'OR', 'NOT', 'TRUE_DOMAIN', 'FALSE_DOMAIN', 'to_q']
