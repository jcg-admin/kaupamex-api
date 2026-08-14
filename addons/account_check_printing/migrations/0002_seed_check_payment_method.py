"""Siembra el método de pago «Checks» + backfill de diarios de banco.

≙ el ``data/`` de la referencia (registro ``account_payment_method_check``)
más su ``post_init_hook`` (``create_check_sequence_on_bank_journals``) — ver
``data/check_payment_method.py`` para la medición y el detalle de cada
función.

Esta migración **no agrega columnas** — sólo filas en tablas ya existentes
(``account_payment_method``, ``ir_model_data``, ``account_check_printing_
journal_settings``, ``ir_sequence``). No depende del wiring pendiente de
``INSTALLED_APPS`` para EXISTIR, sólo para ejecutarse (Django no corre
migraciones de una app que no está registrada) — mismo criterio que
``account_fleet/migrations/0001_seed_fleet_service_type_vendor_bill.py``.
"""
from django.db import migrations

from addons.account_check_printing.data import (
    seed_bank_journal_check_sequences,
    seed_check_payment_method,
)


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias
    seed_check_payment_method(apps, alias)
    seed_bank_journal_check_sequences(apps, alias)


class Migration(migrations.Migration):

    dependencies = [
        ('account_check_printing', '0001_initial'),
        ('account', '0004_accountpaymentmethod_accountpaymentmethodline_and_more'),
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
