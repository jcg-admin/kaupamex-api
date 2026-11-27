"""``ir.actions.actions`` y ``act_window_close`` con la forma de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_actions.py:55-60,428-443`` y
``odoo/addons/base/security/ir.model.access.csv:100,102``. Diseño:
``designs/ir-actions-actions-basemodel.md``.

``act_window_close`` deja de ser un ``proxy`` y pasa a modelo concreto con
``managed = False`` sobre ``ir_actions``: ninguna de las dos operaciones toca
la base, porque Django no migra ni un ``proxy`` ni un modelo no gestionado.
"""

import orm.fields_temporal
import orm.models
from django.db import migrations, models

from addons.base.security.ir_model_access import seed_base_acl


def seed(apps, schema_editor):
    seed_base_acl(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0144_ir_embedded_actions_basemodel"),
    ]

    operations = [
        migrations.DeleteModel(
            name="IrActionsActWindowClose",
        ),
        migrations.CreateModel(
            name="IrActionsActWindowClose",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("create_date", models.DateTimeField(auto_now_add=True)),
                ("write_date", models.DateTimeField(auto_now=True)),
                (
                    "name",
                    models.CharField(
                        max_length=255, verbose_name="Nombre de la acción"
                    ),
                ),
                (
                    "path",
                    models.CharField(
                        blank=True,
                        default=None,
                        help_text=(
                            "Debe ser única (Odoo _path_unique). default=None,"
                            " no '': la referencia declara el campo sin "
                            "default (``path = fields.Char(...)``, odoo19c: "
                            "ir_actions.py:70) y un Char sin valor se escribe "
                            "NULL en Odoo, no cadena vacía — con NULL el "
                            "UNIQUE admite múltiples acciones sin ruta "
                            "(H-API-332: default='' colisionaba en la segunda "
                            "ir.actions.server creada sin path explícito)."
                        ),
                        max_length=64,
                        null=True,
                        unique=True,
                        verbose_name="Ruta en la URL",
                    ),
                ),
                (
                    "help",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text=(
                            "Texto de ayuda opcional que describe la vista "
                            "destino."
                        ),
                        verbose_name="Descripción de la acción",
                    ),
                ),
                (
                    "binding_model_name",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        default="",
                        help_text=(
                            "Odoo binding_model_id. Con valor, la acción "
                            "aparece en la barra lateral de ese modelo."
                        ),
                        max_length=120,
                        verbose_name="Modelo de anclaje",
                    ),
                ),
                (
                    "binding_type",
                    models.CharField(
                        choices=[("action", "Acción"), ("report", "Reporte")],
                        default="action",
                        max_length=16,
                        verbose_name="Tipo de anclaje",
                    ),
                ),
                (
                    "binding_view_types",
                    models.CharField(
                        default="list,form",
                        max_length=64,
                        verbose_name="Vistas de anclaje",
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        default="ir.actions.act_window_close",
                        max_length=64,
                        verbose_name="Tipo de acción",
                    ),
                ),
            ],
            options={
                "verbose_name": "Acción de cierre de ventana",
                "verbose_name_plural": "Acciones de cierre de ventana",
                "db_table": "ir_actions",
                "managed": False,
            },
            bases=(
                orm.models.DefaultGetMixin,
                orm.fields_temporal.TransactionClockSaveMixin,
                orm.models.RecordLoaderMixin,
                orm.models.DisplayNameMixin,
                orm.models.OrderMixin,
                orm.models.CheckCompanyMixin,
                orm.models.BaseUrlMixin,
                orm.models.ArchiveMixin,
                models.Model,
            ),
        ),
        # Sin marcha atrás, mismo criterio que ``0139``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
