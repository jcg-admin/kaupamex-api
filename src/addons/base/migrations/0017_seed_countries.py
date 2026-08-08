"""Siembra los 251 países y sus 8 agrupaciones.

≙ la carga de ``odoo19c: odoo/addons/base/data/res_country_data.xml``, que la
referencia hace al instalar ``base``. Aquí es una data-migration porque este
puerto no tiene el cargador de XML de datos de Odoo: el mecanismo equivalente
es el mismo que ya usa ``account: 0012_seed_account_tags``.

Sin esta migración, tres mecanismos ya escritos quedaban inertes — el país de
las etiquetas fiscales, el que ``create_tax_tags`` asigna, y
``account_fiscal_country`` de la empresa. Ver :ref:`h-api-358`.
"""
from django.db import migrations

from addons.base.data.res_country_data import seed_countries


def seed(apps, schema_editor):
    seed_countries(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0016_rescountry_address_format_rescountry_name_position_and_more'),
    ]

    operations = [
        # Sin marcha atrás: `noop` y no un borrado. Quitar los países dejaría
        # sin resolver toda FK que ya los apunte — y el objetivo de revertir
        # esta migración sería volver al esquema, no vaciar el catálogo.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
