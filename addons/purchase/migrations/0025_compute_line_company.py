"""Calcula ``company_id`` de las líneas existentes: el campo pasa a
``related='order_id.company_id', store=True`` (``0023``).

Guardián: ``tests/unit/orm/test_new_computed_columns_are_computed.py``
(TASK-API-0516). Las filas ya traían el valor de la sincronización en
``save()``; el cómputo deja la columna derivada de la orden, como la fuente.
"""
from django.db import migrations

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("purchase", "0024_line_name_discount_without_default"),
    ]

    operations = [
        ComputeStoredFields(
            "purchase", "purchaseorderline", ["company_id"]),
    ]
