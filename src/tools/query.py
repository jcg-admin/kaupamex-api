"""``Query`` — fiel a ``odoo/tools/query.py`` (Odoo 18/19).

Odoo expone ``odoo.tools.Query`` (constructor de SELECT componibles). Aquí, con
el prefijo ``odoo.`` eliminado (convención del proyecto: ``tools`` ≙
``odoo/tools``), un addon escribe ``from tools.query import Query`` — leyendo
como su fuente Odoo.

Respaldo Django: ``Query`` = ``django.db.models.QuerySet`` (la abstracción
componible de consultas de Django, equivalente al rol de ``odoo.tools.Query``).
"""
from django.db import models

__all__ = ['Query']

Query = models.QuerySet            # Odoo tools.Query ≈ Django QuerySet
