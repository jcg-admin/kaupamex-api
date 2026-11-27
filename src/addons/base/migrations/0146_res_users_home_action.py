"""``res.users.action_id`` y el ``type`` por defecto de cada subtipo.

≙ ``odoo19c: odoo/addons/base/models/res_users.py:229-230`` y los
``type = fields.Char(default=...)`` de cada subtipo de acción
(``ir_actions.py:308,453,607,1434``; ``ir_actions_report.py:165-166``).
Diseño: ``designs/res-users-home-action.md``. La columna ``action_id`` es
nueva y anulable, sin clave foránea porque ``ir_actions`` se hereda; los
valores por defecto sólo cambian el estado: Django no los escribe en la base.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0145_ir_actions_actions_basemodel"),
    ]

    operations = [
        migrations.AddField(
            model_name="resusers",
            name="action_id",
            field=models.ForeignKey(
                blank=True,
                db_column="action_id",
                db_constraint=False,
                help_text=(
                    "If specified, this action will be opened at log on for "
                    "this user, in addition to the standard menu."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="base.iractionsactions",
                verbose_name="Home Action",
            ),
        ),
        migrations.AlterField(
            model_name="iractionsacturl",
            name="type",
            field=models.CharField(
                default="ir.actions.act_url",
                max_length=64,
                verbose_name="Tipo de acción",
            ),
        ),
        migrations.AlterField(
            model_name="iractionsactwindow",
            name="type",
            field=models.CharField(
                default="ir.actions.act_window",
                max_length=64,
                verbose_name="Tipo de acción",
            ),
        ),
        migrations.AlterField(
            model_name="iractionsclient",
            name="type",
            field=models.CharField(
                default="ir.actions.client",
                max_length=64,
                verbose_name="Tipo de acción",
            ),
        ),
        migrations.AlterField(
            model_name="iractionsreport",
            name="binding_type",
            field=models.CharField(
                choices=[("action", "Acción"), ("report", "Reporte")],
                default="report",
                max_length=16,
                verbose_name="Tipo de anclaje",
            ),
        ),
        migrations.AlterField(
            model_name="iractionsreport",
            name="type",
            field=models.CharField(
                default="ir.actions.report",
                max_length=64,
                verbose_name="Tipo de acción",
            ),
        ),
        migrations.AlterField(
            model_name="iractionsserver",
            name="type",
            field=models.CharField(
                default="ir.actions.server",
                max_length=64,
                verbose_name="Tipo de acción",
            ),
        ),
    ]
