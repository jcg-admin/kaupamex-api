"""``country_ids`` de ``ir.module.module`` con la tabla de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_module.py:297``:
``fields.Many2many('res.country', 'module_country', 'module_id',
'country_id')``. Crea la tabla ``module_country`` con esas dos columnas, que
son las que escriben ``_update_countries`` (``:842-850``) y lee
``res.company._compute_uninstalled_l10n_module_ids``. Diseño:
``designs/ir-module-country-ids.md``.
"""

from django.db import migrations

import orm.fields_relational


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0156_ir_module_versions'),
    ]

    operations = [
        migrations.AddField(
            model_name='irmodule',
            name='country_ids',
            field=orm.fields_relational.Many2manyField(
                blank=True,
                column1='module_id',
                column2='country_id',
                db_table='module_country',
                related_name='+',
                to='base.rescountry',
            ),
        ),
    ]
