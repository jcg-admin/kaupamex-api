"""Campo de selección — fiel a ``odoo/orm/fields_selection.py`` (Odoo 19).

``Selection`` = ``CharField(choices=…)`` en Django.
"""
from django.db import models

__all__ = ['Selection']

Selection = models.CharField          # Odoo Selection ≈ CharField(choices=…)
