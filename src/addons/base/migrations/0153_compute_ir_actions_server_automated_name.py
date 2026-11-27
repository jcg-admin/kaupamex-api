"""Calcula ``automated_name`` sobre las acciones de servidor existentes.

``automated_name`` entró por ``AddField`` en 0061 y ahora es un calculado
almacenado (``odoo19c: odoo/addons/base/models/ir_actions.py:606``): sus
filas se calculan como las de una columna calculada nueva
(``odoo19c: odoo/orm/models.py:3220-3238``).
"""

from django.db import migrations

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0152_alter_iractionsserver_automated_name'),
    ]

    operations = [
        ComputeStoredFields('base', 'iractionsserver', ['automated_name']),
    ]
