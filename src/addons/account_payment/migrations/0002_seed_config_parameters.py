"""Siembra ``account_payment.enable_portal_payment`` — ≙ el ``data/`` de la
referencia.

Ver ``data/config_parameters.py`` para la medición y por qué no hace falta
``ir.model.data`` aquí (``SystemParameter`` se identifica por ``key``).

Depende de ``account_payment.0001_initial`` (existencia de la app en el
grafo de migraciones) y de ``base.0001_initial`` (tabla ``system_parameter``,
``SystemParameter``).
"""
from django.db import migrations

from addons.account_payment.data import seed_config_parameters


def seed(apps, schema_editor):
    seed_config_parameters(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('account_payment', '0001_initial'),
        ('base', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
