"""Objetos de tabla del ORM — fiel a ``odoo/orm/table_objects.py`` (Odoo 19).

Odoo modela constraints e índices SQL como objetos declarativos
(``Constraint``, ``Index``, ``UniqueIndex``) que el ORM materializa en el schema
al arrancar. Es la contraparte de bajo nivel de ``_sql_constraints``.

Mapeo a Django — **Django ya es el motor de schema**, así que estos objetos se
expresan con las primitivas nativas y no se reimplementan:

===============================  =====================================================
Odoo ``table_objects``           Equivalente Django (idiomático)
===============================  =====================================================
``Constraint('name', sql)``      ``Meta.constraints = [CheckConstraint(...)]`` o
                                 ``UniqueConstraint(...)``
``Index('name', fields)``        ``Meta.indexes = [Index(fields=[...])]``
``UniqueIndex('name', fields)``  ``Meta.constraints = [UniqueConstraint(fields=[...])]``
                                 (o ``unique=True`` / ``unique_together``)
===============================  =====================================================

Se re-exportan las clases nativas de Django bajo los **nombres Odoo** para que un
addon portado que lea ``from orm.table_objects import UniqueIndex`` obtenga el
constructo correcto. ``makemigrations`` los materializa en el schema — el ORM de
Django hace lo que en Odoo hacía ``table_objects`` al boot.
"""
from django.db.models import CheckConstraint  # noqa: F401  (Odoo: Constraint check)
from django.db.models import Index             # noqa: F401  (Odoo: Index)
from django.db.models import UniqueConstraint  # noqa: F401  (Odoo: UniqueIndex)

# Alias con el nombre Odoo → constructo Django nativo.
Constraint = CheckConstraint   # ``Constraint('name', 'CHECK(...)')`` → CheckConstraint
UniqueIndex = UniqueConstraint  # ``UniqueIndex('name', fields)``    → UniqueConstraint

__all__ = ['Constraint', 'Index', 'UniqueIndex', 'CheckConstraint', 'UniqueConstraint']
