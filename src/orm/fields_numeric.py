"""Campos numéricos — fiel a ``odoo/orm/fields_numeric.py`` (Odoo 19).

``Integer``, ``Float``, ``Monetary`` (Odoo Monetary = importe con moneda; alias
de ``DecimalField`` que en el proyecto sale como string por
``COERCE_DECIMAL_TO_STRING``).
"""
from django.db import models

__all__ = ['Integer', 'Float', 'Monetary']

Integer = models.IntegerField
Float = models.FloatField
Monetary = models.DecimalField
