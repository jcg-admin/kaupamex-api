"""``models`` — fiel a ``odoo/models/__init__.py`` (Odoo 19).

Re-export del ORM base definido en ``orm/models.py`` (≙ ``odoo/orm/models.py``),
para que un addon escriba ``import models`` / ``class X(models.Model)`` leyendo
como su fuente Odoo (``from odoo import models``). Igual que Odoo separa la
definición (``odoo/orm/models.py``) de su superficie pública
(``odoo/models/__init__.py``), aquí la definición vive en ``orm/models.py`` y
este módulo top-level es sólo la re-exportación.
"""
from orm.models import *             # noqa: F401,F403  (re-export de orm/models)
from orm.models import Model         # noqa: F401  (explícito: base de modelo)
