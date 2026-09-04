"""El asistente de historial gana su tabla.

Un ``TransientModel`` de la fuente **tiene tabla real** —``_auto = True``,
``odoo19c: odoo/orm/models_transient.py:18``—; aquí la base la declaraba
``managed = False``, así que ``server_action_history_wizard`` nunca se creó y
su suite fallaba con ``relation … does not exist``.

**Por qué ``SeparateDatabaseAndState`` y no un ``CreateModel`` a secas.** El
estado de migraciones ya conoce el modelo con sus tres columnas: se registró
cuando era no gestionado. Un ``CreateModel`` normal lo declararía por segunda
vez y el estado quedaría inconsistente. Medido antes de escribir esto:
``sqlmigrate`` sobre la versión que sólo llevaba ``AlterModelOptions`` emitía
``-- (no-op)``, que es exactamente el defecto — cambiar ``managed`` no crea la
tabla.

Así que la tabla se crea **sólo en la base** y el estado recibe únicamente el
cambio de opciones, que es lo que de verdad cambió en él.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0071_report_type_se_queda_solo_con_pdf"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.CreateModel(
                    name="ServerActionHistoryWizard",
                    fields=[
                        ("id", models.BigAutoField(
                            auto_created=True, primary_key=True,
                            serialize=False, verbose_name="ID")),
                        ("action", models.ForeignKey(
                            blank=True, null=True,
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name="history_wizards",
                            to="base.iractionsserver", verbose_name="Acción")),
                        ("revision", models.ForeignKey(
                            blank=True, null=True,
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name="wizards",
                            to="base.iractionsserverhistory",
                            verbose_name="Revisión")),
                    ],
                    options={
                        "db_table": "server_action_history_wizard",
                        "verbose_name":
                            "Asistente de historial de acción de servidor",
                        "verbose_name_plural":
                            "Asistentes de historial de acción de servidor",
                    },
                ),
            ],
            state_operations=[
                migrations.AlterModelOptions(
                    name="serveractionhistorywizard",
                    options={
                        "verbose_name":
                            "Asistente de historial de acción de servidor",
                        "verbose_name_plural":
                            "Asistentes de historial de acción de servidor",
                    },
                ),
                # El estado tenía el modelo con SOLO su ``id``: al crearlo
                # ``0061`` como no gestionado, sus dos claves ajenas nunca
                # entraron. La base ya las tiene por el ``CreateModel`` de
                # arriba, así que aquí se alinea el estado con ella.
                migrations.AddField(
                    model_name="serveractionhistorywizard",
                    name="action",
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="history_wizards",
                        to="base.iractionsserver", verbose_name="Acción"),
                ),
                migrations.AddField(
                    model_name="serveractionhistorywizard",
                    name="revision",
                    field=models.ForeignKey(
                        blank=True, null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wizards",
                        to="base.iractionsserverhistory",
                        verbose_name="Revisión"),
                ),
            ],
        ),
    ]
