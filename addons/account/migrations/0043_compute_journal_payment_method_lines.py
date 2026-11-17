"""Da sus líneas de método de pago por defecto a los diarios existentes.

``inbound_payment_method_line_ids`` y ``outbound_payment_method_line_ids``
pasan a ser calculados almacenados (``odoo19c: addons/account/models/
account_journal.py:205-233,462-504``). No añaden columna —la guarda la
línea—, pero los diarios que ya existían nunca pasaron por el cómputo: la
fuente los calcula al crear el campo (``odoo19c: odoo/orm/models.py:
3220-3238``). Depende de ``0042``, que siembra los métodos manuales.
"""
from django.db import migrations

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0042_seed_manual_payment_methods'),
    ]

    operations = [
        ComputeStoredFields(
            'account', 'accountjournal',
            ['inbound_payment_method_line_ids',
             'outbound_payment_method_line_ids']),
    ]
