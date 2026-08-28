"""``models`` — fiel a ``odoo/models/__init__.py`` (Odoo 19).

Paquete (no módulo suelto), igual que ``odoo/models/`` es un paquete. Re-exporta
el ORM base definido en ``orm/models.py`` (≙ ``odoo/orm/models.py``). Un addon
escribe ``import models`` / ``class X(models.Model)`` leyendo como su fuente Odoo
(``from odoo import models``). La definición vive en ``orm/``; este paquete es la
superficie pública.
"""
from orm.models import *             # noqa: F401,F403  (re-export de orm/models)
from orm.models import Model         # noqa: F401  (explícito: base de modelo)
from orm.models import OriginMixin   # noqa: F401  (explícito: el _origin de la fuente)
