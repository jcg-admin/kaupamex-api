"""Campos de propiedades dinámicas — fiel a ``odoo/orm/fields_properties.py``.

Odoo ``Properties``/``PropertiesDefinition`` = propiedades dinámicas por registro
(esquema definido en un padre). En Django el equivalente natural es
``JSONField`` (esquema validado en el serializer/clean). Alias de lectura.
"""
from django.db import models

__all__ = ['Properties', 'PropertiesDefinition']

Properties = models.JSONField
PropertiesDefinition = models.JSONField
