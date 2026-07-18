"""Base del ORM — fiel a ``odoo/orm/models.py`` (Odoo 19).

En Odoo 19 la clase base ``BaseModel``/``Model`` se define en
``odoo/orm/models.py`` y ``odoo/models/__init__.py`` la re-exporta. Aquí, con el
prefijo ``odoo.`` eliminado (``orm`` ≙ ``odoo/orm``), esta es la **definición**;
``src/models.py`` (top-level, ≙ ``odoo/models/__init__.py``) la re-exporta para
que un addon escriba ``import models`` / ``class X(models.Model)``.

Respaldo: ``models`` ES la ORM de Django — se re-exporta ``django.db.models``
completo (``Model``, ``Manager``, ``UniqueConstraint``, ``Index``, ``CASCADE``/
``SET_NULL``/``PROTECT``, ``Q``, ``Sum``, ``F``…). No se interpone una capa;
sólo se expone bajo el nombre Odoo para que el addon lea igual que su fuente.
"""
from django.db.models import *          # noqa: F401,F403  (re-export ORM completo)
from django.db.models import Model      # noqa: F401  (explícito: base de modelo)
