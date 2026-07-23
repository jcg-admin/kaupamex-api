"""Campos binarios — fiel a ``odoo/orm/fields_binary.py`` (Odoo 19).

``Binary`` = ``BinaryField``; Odoo ``Image`` = alias de imagen (``ImageField``).
"""
from django.db import models

__all__ = ['Binary', 'Image']

Binary = models.BinaryField
Image = models.ImageField             # Odoo Image ≈ ImageField
