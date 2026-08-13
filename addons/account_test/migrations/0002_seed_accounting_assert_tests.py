"""Siembra los seis registros de prueba — ≙ el ``data/`` de la referencia.

Sin ella, el menú *Accounting Tests* de la referencia estaría vacío al
instalar. Ver ``data/accounting_assert_tests.py`` para el contenido exacto
y las divergencias declaradas (``account_invoice`` ausente,
``account_move_line.date`` deferido).

``base`` entra en las dependencias porque la fila del identificador externo
vive en ``ir.model.data``, de ese addon — mismo criterio que
``account_fleet/migrations/0001_seed_fleet_service_type_vendor_bill.py``.
No depende de ``account`` porque esta migración sólo escribe en
``account_test_accounting_assert_test`` (esta app) e ``ir_model_data``
(``base``): ``AccountingAssertTest`` no tiene FK a ningún modelo de
``account`` (ver ``models/accounting_assert_test.py`` — el modelo es
standalone; ``reconciled_inv()``/las consultas de ``code_exec`` son texto
o código ejecutado en runtime, no columnas de esta migración).
"""
from django.db import migrations

from addons.account_test.data import seed_accounting_assert_tests


def seed(apps, schema_editor):
    seed_accounting_assert_tests(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('account_test', '0001_initial'),
        ('base', '0019_respartnerbank_include_reference_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
