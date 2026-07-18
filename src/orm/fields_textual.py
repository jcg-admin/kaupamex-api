"""Campos textuales — fiel a ``odoo/orm/fields_textual.py`` (Odoo 19).

``Char`` y ``Text`` (Odoo también ``Html``: ≈ ``TextField`` + saneo con
``dompurify`` en UI; se expone como alias de ``TextField``). Alias de nombre
Odoo → clase Django (firma Django).
"""
from django.db import models

__all__ = ['Char', 'Text', 'Html']

Char = models.CharField
Text = models.TextField
Html = models.TextField               # Odoo Html ≈ TextField (saneo en capa UI)
