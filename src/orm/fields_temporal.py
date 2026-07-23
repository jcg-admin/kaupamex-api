"""Campos temporales — fiel a ``odoo/orm/fields_temporal.py`` (Odoo 19).

``Date`` y ``Datetime``.
"""
from django.db import models

__all__ = ['Date', 'Datetime']

Date = models.DateField
Datetime = models.DateTimeField
