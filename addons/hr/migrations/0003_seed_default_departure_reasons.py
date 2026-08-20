"""Siembra los tres motivos de baja maestros — ≙ ``odoo19c: hr/data/hr_data.xml:56-73``.

Sin ellos ``HrDepartureReason._get_default_departure_reasons()`` no resuelve
nada y su guarda de borrado (``delete()``) queda sin efecto — mismo patrón
que ``account/migrations/0012_seed_account_tags.py`` resuelve para las tres
etiquetas maestras de ``account.account.tag`` en este mismo árbol.

La tabla y la lógica viven en ``addons/hr/data/hr_departure_reason_data.py``,
no aquí: esta migración las siembra **una vez**, y el catálogo de
``tests/conftest.py`` las repone tras cada flush. Dos copias de la misma
tabla serían dos fuentes de verdad que nadie sincroniza.

``base`` entra en las dependencias porque la fila del identificador externo
vive en ``ir.model.data``, que es de ese addon.
"""
from django.db import migrations

from addons.hr.data.hr_departure_reason_data import seed_departure_reasons


def seed(apps, schema_editor):
    seed_departure_reasons(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('hr', '0002_hrcontracttype_hrdeparturereason_hremployeecategory_and_more'),
        ('base', '0024_respartner_check_name'),
    ]

    operations = [
        # Sin marcha atrás: `noop` y no un borrado. Quitar los motivos dejaría
        # sin resolver toda FK que ya los apunte, y revertir esta migración
        # busca volver al esquema, no vaciar el catálogo.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
