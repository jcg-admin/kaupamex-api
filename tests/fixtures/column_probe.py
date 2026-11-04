"""Sonda de columna: dice si un campo quedó con columna al contribuirlo.

Es el contrato de la fuente (``odoo19c: odoo/orm/fields.py:455``): un campo
no almacenado no tiene columna. Desde TASK-API-0417 la forma sin columna la
decide la costura al contribuir —``private_only`` y ``column=None``—, no la
clase que devuelve el constructor, así que se mide ahí y no con
``isinstance``. ``isolate_apps`` evita registrar el modelo y crear tablas.

Vive aquí y no en cada archivo de prueba para que la medición tenga una sola
copia.
"""

import itertools

from django.db import models
from django.test.utils import isolate_apps

_HOLDERS = itertools.count()


def has_column(field):
    """Contribuye ``field`` a un modelo aislado y dice si quedó con columna."""
    with isolate_apps():
        meta = type('Meta', (), {'app_label': 'base'})
        model = type(f'ColumnHolder{next(_HOLDERS)}', (models.Model,), {
            '__module__': __name__, 'probe': field, 'Meta': meta})
    return (getattr(field, 'column', None) is not None
            and field in model._meta.local_fields)
