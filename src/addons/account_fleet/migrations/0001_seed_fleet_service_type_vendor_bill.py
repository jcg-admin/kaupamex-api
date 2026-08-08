"""Siembra el tipo de servicio «Vendor Bill» — ≙ el ``data/`` de la referencia.

Sin él, ``models/account_move.py::_create_fleet_service_bills_on_post`` no
crea ningún servicio al postear una factura con vehículo (mismo guard que la
referencia). Ver ``data/fleet_service_types.py`` para la medición.

``fleet`` entra en las dependencias porque siembra en su tabla
(``FleetServiceType``); ``base`` porque la fila del identificador externo
vive en ``ir.model.data``, de ese addon — mismo criterio que
``account/migrations/0012_seed_account_tags.py``.

Esta migración **no agrega columnas** — sólo filas en tablas ya existentes
(``fleet_service_type``, ``ir_model_data``). No depende del wiring pendiente
de ``INSTALLED_APPS`` para EXISTIR, sólo para ejecutarse (Django no corre
migraciones de una app que no está registrada) — ver ``__init__.py`` del
paquete, sección "Wiring pendiente".
"""
from django.db import migrations

from addons.account_fleet.data import seed_fleet_service_types


def seed(apps, schema_editor):
    seed_fleet_service_types(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('fleet', '0002_fleetvehicle_name'),
        ('base', '0018_rescompany_account_fiscal_country'),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
