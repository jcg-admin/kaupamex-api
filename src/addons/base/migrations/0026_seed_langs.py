"""Siembra los 93 idiomas de la referencia, con ``en_US`` activo.

≙ la carga de ``odoo19c: odoo/addons/base/data/res.lang.csv`` más el
``install_lang`` de ``res_lang_data.xml``, que la referencia hace al instalar
``base``. Aquí es una data-migration por la misma razón que
``0017_seed_countries``: este puerto no tiene el cargador de datos de Odoo.

Sin esta migración ``res_lang`` nacía vacía, y con ella quedaba inerte todo lo
que necesita un idioma por defecto — empezando por ``Website.default_lang``,
que es ``required`` y cuyo ``_default_language`` no tiene de dónde sacar valor
sobre una tabla sin filas. Ver :ref:`h-api-696`.
"""
from django.db import migrations

from addons.base.data.res_lang_data import seed_langs


def seed(apps, schema_editor):
    seed_langs(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0025_alter_respartner_options_alter_resusers_options'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que los países: borrar el catálogo
        # dejaría sin resolver toda FK que ya lo apunte, y revertir esta
        # migración busca volver al esquema, no vaciar la tabla.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
