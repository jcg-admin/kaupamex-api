"""Campos del ORM — fiel a ``odoo/orm/fields*.py`` (Odoo 19).

En Odoo 19 los campos se **definen** en ``odoo/orm/fields.py`` +
``odoo/orm/fields_{textual,numeric,temporal,relational,selection,misc,binary}.py``
y ``odoo/fields/__init__.py`` los re-exporta. Aquí, con el prefijo ``odoo.``
eliminado (``orm`` ≙ ``odoo/orm``), esta es la **definición** consolidada;
``src/fields.py`` (top-level, ≙ ``odoo/fields/__init__.py``) la re-exporta.

Cada nombre mapea el **nombre** de campo de Odoo → la clase de Django. La
**firma** difiere (Odoo ``Char(string=…, required=True)`` vs Django
``CharField(max_length=…)``): alias de lectura con parámetros Django; un
adaptador de firmas 1:1 sería una sub-iniciativa (``fields``-signature-shim).
``One2many`` no tiene clase Django (es el reverso de un FK vía ``related_name``).
"""
from django.db import models

__all__ = [
    'Char', 'Text', 'Boolean', 'Integer', 'Float', 'Monetary', 'Date',
    'Datetime', 'Selection', 'Many2one', 'One2many', 'Many2many', 'Binary',
    'Json',
]

# Nombres de campo de Odoo → clases de Django (alias de lectura).
Char = models.CharField
Text = models.TextField
Boolean = models.BooleanField
Integer = models.IntegerField
Float = models.FloatField
Monetary = models.DecimalField
Date = models.DateField
Datetime = models.DateTimeField
Selection = models.CharField          # Odoo Selection ≈ CharField(choices=…)
Many2one = models.ForeignKey
One2many = None                       # reverso de FK en Django (related_name)
Many2many = models.ManyToManyField
Binary = models.BinaryField
Json = models.JSONField
