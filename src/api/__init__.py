"""``api`` — fiel a ``odoo/api/__init__.py`` (Odoo 19).

Paquete (no módulo suelto), igual que ``odoo/api/`` es un paquete. Re-exporta los
decoradores definidos en ``orm/decorators.py`` (≙ ``odoo/orm/decorators.py``,
que ``odoo/api/__init__.py`` re-exporta). Un addon escribe ``import api`` y usa
``@api.depends(...)`` / ``@api.constrains(...)`` leyendo como su fuente Odoo
(``from odoo import api``). La definición vive en ``orm/``; este paquete es la
superficie pública.
"""
from orm.decorators import (          # noqa: F401  (re-export de orm/decorators)
    autovacuum,
    constrains,
    depends,
    model,
    model_create_multi,
    onchange,
    returns,
)

__all__ = [
    'depends', 'constrains', 'onchange', 'model', 'model_create_multi', 'returns',
    'autovacuum',
]
