"""Nombres de campo — fiel a ``odoo/fields`` (Odoo 18/19).

Módulo top-level (prefijo ``odoo.`` eliminado por la convención del proyecto):
un addon escribe ``import fields`` y usa ``fields.Char(...)``, leyendo como su
fuente Odoo (``from odoo import fields``).

Cada nombre mapea al **nombre** de campo de Odoo → la clase de Django. La
**firma** difiere (Odoo ``fields.Char(string=…, required=True)`` vs Django
``CharField(max_length=…, verbose_name=…)``): se exponen como alias de clase
para lectura/consistencia; un adaptador de firmas 1:1 sería una sub-iniciativa
(``fields``-signature-shim), no se half-buildea aquí.

``models`` (base de modelo) NO se re-exporta: en este proyecto un addon usa
``from django.db import models`` directamente — ``models`` ES la ORM de Django.
"""
from django.db import models

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
