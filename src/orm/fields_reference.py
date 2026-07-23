"""Campos de referencia — fiel a ``odoo/orm/fields_reference.py`` (Odoo 19).

Odoo ``Reference``/``Many2oneReference`` = FK polimórfico (``'model,id'``). En
Django el equivalente es ``GenericForeignKey`` (framework ``contenttypes``), que
requiere un par ``content_type`` (FK) + ``object_id``; no es una única clase de
campo. Se expone el nombre para lectura; el cableado concreto se hace con
``contenttypes`` en el modelo que lo requiera (aún ningún addon portado lo usa).
"""
from django.contrib.contenttypes.fields import GenericForeignKey

__all__ = ['Reference', 'Many2oneReference']

Reference = GenericForeignKey         # requiere content_type + object_id
Many2oneReference = GenericForeignKey
