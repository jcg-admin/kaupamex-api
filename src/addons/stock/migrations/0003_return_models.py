"""Crea los modelos de devolución (RMA) en ``stock``.

El RMA se aloja en ``stock`` (hogar fiel: devolución = return picking de Odoo);
las tablas conservan el nombre histórico ``return_*`` vía ``db_table``.

**H-API-21 (2026-07-28):** nació ``state-only`` porque las tablas ya existían,
creadas por la ex-migración ``returns.0001``. Al plegarse ``returns`` en
``stock`` esa migración se eliminó del árbol y nadie quedó creando las tablas:
todo build *desde cero* moría con ``Table 'return_request' doesn't exist``.
Se restituye la creación real. Mismo defecto que ``rating.0001_initial``.
"""
import addons.stock.models.return_request
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stock", "0002_stocklot_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    state_operations = [
        migrations.CreateModel(
            name="ReturnRequest",
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
                    "is_deleted",
                    models.BooleanField(
                        db_index=True,
                        default=False,
                        help_text="True si la fila fue borrada via soft delete.",
                        verbose_name="Eliminado (logico)",
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Fecha de borrado logico"
                    ),
                ),
                ("order_id", models.PositiveIntegerField()),
                (
                    "reason",
                    models.CharField(
                        choices=[
                            ("DAMAGED_PRODUCT", "Producto danado"),
                            ("NOT_AS_DESCRIBED", "No coincide con la descripcion"),
                            ("CHANGED_MIND", "Cambio de opinion"),
                            ("OTHER", "Otro"),
                        ],
                        max_length=24,
                    ),
                ),
                ("description", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING_REVIEW", "Pendiente de revision"),
                            ("INFO_REQUESTED", "Pendiente de informacion"),
                            ("APPROVED", "Aprobada"),
                            ("REJECTED", "Rechazada"),
                            ("RECEIVED", "Recibida"),
                            ("REFUNDED", "Reembolsada"),
                        ],
                        default="PENDING_REVIEW",
                        max_length=16,
                    ),
                ),
                (
                    "refund_amount",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=10, null=True
                    ),
                ),
                ("refund_at", models.DateTimeField(blank=True, null=True)),
                ("received_at", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True, default="")),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="return_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Solicitud de devolucion",
                "verbose_name_plural": "Solicitudes de devolucion",
                "db_table": "return_request",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ReturnItem",
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
                ("product_id", models.PositiveIntegerField()),
                ("quantity", models.PositiveIntegerField(default=1)),
                (
                    "product_condition",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("GOOD_CONDITION", "Buenas condiciones"),
                            ("DAMAGED", "Danado"),
                            ("INCOMPLETE", "Incompleto"),
                        ],
                        default="",
                        max_length=16,
                    ),
                ),
                (
                    "return_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="stock.returnrequest",
                    ),
                ),
            ],
            options={
                "verbose_name": "Item de devolucion",
                "verbose_name_plural": "Items de devolucion",
                "db_table": "return_item",
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="ReturnHistoryEntry",
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
                    "status_to",
                    models.CharField(
                        choices=[
                            ("PENDING_REVIEW", "Pendiente de revision"),
                            ("INFO_REQUESTED", "Pendiente de informacion"),
                            ("APPROVED", "Aprobada"),
                            ("REJECTED", "Rechazada"),
                            ("RECEIVED", "Recibida"),
                            ("REFUNDED", "Reembolsada"),
                        ],
                        max_length=16,
                    ),
                ),
                ("justification", models.TextField(blank=True, default="")),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="return_history_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "return_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="history_entries",
                        to="stock.returnrequest",
                    ),
                ),
            ],
            options={
                "verbose_name": "Entrada de historial de devolucion",
                "verbose_name_plural": "Entradas de historial de devoluciones",
                "db_table": "return_history_entry",
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="ReturnEvidence",
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
                    "image",
                    models.ImageField(
                        upload_to=addons.stock.models.return_request.return_evidence_upload_path
                    ),
                ),
                (
                    "return_request",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="evidence",
                        to="stock.returnrequest",
                    ),
                ),
            ],
            options={
                "verbose_name": "Evidencia de devolucion",
                "verbose_name_plural": "Evidencias de devolucion",
                "db_table": "return_evidence",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="returnrequest",
            index=models.Index(
                fields=["user", "status"], name="return_requ_user_id_24a4d0_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="returnrequest",
            index=models.Index(
                fields=["status", "created_at"], name="return_requ_status_f0f3fe_idx"
            ),
        ),
    ]

    # H-API-21: las operaciones se aplican a la BD, no sólo al estado.
    operations = state_operations
