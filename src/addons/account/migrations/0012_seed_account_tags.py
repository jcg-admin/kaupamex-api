"""Siembra las tres etiquetas maestras — ≙ el bloque de ``account_data.xml``.

Sin ellas la columna ``tag_ids`` del plan genérico no resuelve: 13 de sus 46
cuentas la traen, y las dos de diferencia de efectivo la reciben del propio
cargador. Ver ``addons/account/data/account_tags.py`` para la medición.

``base`` entra en las dependencias porque la fila del identificador externo
vive en ``ir.model.data``, que es de ese addon.
"""
from django.db import migrations

from addons.account.data import seed_account_tags


def seed(apps, schema_editor):
    seed_account_tags(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0011_journal_dashboard_fields'),
        ('base', '0013_company_utility_accounts'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
