"""Las versiones de ``ir.module.module`` con los nombres de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_module.py:285-291``. La columna que
guardaba lo instalado se llamaba ``installed_version``; en la fuente esa
columna es ``latest_version`` («the installed version (the one in
database)»), y ``installed_version`` es un campo calculado sin columna. Se
renombra la columna, sin tocar su dato, y se añade ``published_version``.
Diseño: ``designs/ir-module-versions.md``.
"""

from django.db import migrations

import fields


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0155_ir_module_dependency_module_id'),
    ]

    operations = [
        migrations.RenameField(
            model_name='irmodule',
            old_name='installed_version',
            new_name='latest_version',
        ),
        migrations.AlterField(
            model_name='irmodule',
            name='latest_version',
            field=fields.Char(
                'Installed Version', blank=True, null=True, default=None,
                editable=False,
                help_text=('Versión realmente instalada; NULL si no existe '
                           'evidencia de instalación.'),
            ),
        ),
        migrations.AddField(
            model_name='irmodule',
            name='published_version',
            field=fields.Char(
                'Published Version', blank=True, null=True, editable=False),
        ),
    ]
