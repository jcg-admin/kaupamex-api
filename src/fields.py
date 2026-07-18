"""``fields`` — fiel a ``odoo/fields/__init__.py`` (Odoo 19).

Re-export de los campos definidos en ``orm/fields.py`` (≙ ``odoo/orm/fields*.py``)
+ ``Command`` desde ``orm/commands.py`` (≙ ``odoo/orm/commands.py``, que
``odoo/fields/__init__.py`` re-exporta como ``odoo.fields.Command``). Un addon
escribe ``import fields`` y usa ``fields.Char(...)`` / ``fields.Command`` leyendo
como su fuente Odoo (``from odoo import fields``). La definición vive en
``orm/``; este módulo top-level es sólo la superficie pública.
"""
from orm.commands import Command      # noqa: F401  (odoo.fields.Command)
from orm.fields import *              # noqa: F401,F403  (re-export de orm/fields)
