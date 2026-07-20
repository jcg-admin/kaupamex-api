"""Adopta el modelo ``ExportJob`` (export asíncrono de reporte) en ``base``.

State-only (``SeparateDatabaseAndState``): la tabla ``report_export_job`` ya
existe (creada por ``reports.0001_initial``); el registro de estado del export
se re-aloja en ``base`` porque el framework de reportes de Odoo
(``ir.actions.report`` + QWeb) vive en ``base``/``web``, no en un módulo
``reports`` separado. Sólo cambia el ``app_label`` del modelo — sin DDL. La
contraparte ``reports.0002_delete_exportjob`` lo retira del estado de
``reports``.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0011_irdefault"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    state_operations = [
        migrations.CreateModel(
            name="ExportJob",
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
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pendiente"),
                            ("RUNNING", "En proceso"),
                            ("DONE", "Completado"),
                            ("ERROR", "Error"),
                        ],
                        default="PENDING",
                        max_length=10,
                    ),
                ),
                ("file_path", models.CharField(blank=True, default="", max_length=500)),
                ("params", models.JSONField(blank=True, default=dict)),
                ("error_detail", models.TextField(blank=True, default="")),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "requested_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="export_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Export job",
                "verbose_name_plural": "Export jobs",
                "db_table": "report_export_job",
                "ordering": ["-created_at"],
            },
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=state_operations,
            database_operations=[],
        ),
    ]
