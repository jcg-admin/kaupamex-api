"""Campos relacionales — fiel a ``odoo/orm/fields_relational.py`` (Odoo 19).

``Many2one`` = ``ForeignKey``; ``Many2many`` = ``ManyToManyField``; ``One2many``
es el reverso de un FK en Django (``related_name``), sin clase propia.
"""
from django.db import models

__all__ = ['Many2one', 'One2many', 'Many2many']

Many2one = models.ForeignKey
One2many = None                       # reverso de FK (related_name)
Many2many = models.ManyToManyField
