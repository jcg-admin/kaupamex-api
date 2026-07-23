"""Campos misceláneos — fiel a ``odoo/orm/fields_misc.py`` (Odoo 19).

``Boolean``, ``Json`` (Odoo ``Id`` es el pk implícito: en Django lo provee
``AutoField``/``BigAutoField`` automático, no se declara).
"""
from django.db import models

__all__ = ['Boolean', 'Json']

Boolean = models.BooleanField
Json = models.JSONField
