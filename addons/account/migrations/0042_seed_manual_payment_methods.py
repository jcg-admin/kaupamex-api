"""Siembra los métodos de pago manuales de entrada y de salida.

≙ los registros ``account_payment_method_manual_in``/``_out``
(``odoo19c: addons/account/data/account_data.xml:129-138``); ver
``data/payment_methods.py``. Sólo filas: ninguna columna.
"""
from django.db import migrations

from addons.account.data import seed_manual_payment_methods


def seed(apps, schema_editor):
    seed_manual_payment_methods(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0041_restrict_payment_method_line'),
        ('base', '0117_respartner_buyer_id'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
