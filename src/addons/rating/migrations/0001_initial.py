"""Crea los modelos de reseña de producto en ``rating``.

Las reseñas de producto se alojan en ``rating`` (hogar fiel: Odoo construye las
reseñas de producto sobre ``rating.rating`` + ``website_sale``); las tablas
conservan el nombre histórico ``reviews_*`` vía ``db_table``.

**H-API-21 (2026-07-28):** esta migración nació ``state-only``
(``SeparateDatabaseAndState`` con ``database_operations=[]``) porque las tablas
ya existían en el schema desplegado, creadas por la ex-migración
``reviews.0001``. Al plegarse ``reviews`` en ``rating`` esa migración se
eliminó del árbol y **nadie quedó creando las tablas**: cualquier build
*desde cero* moría en ``rating.0002_review_sale_order`` con
``Table 'reviews_review' doesn't exist``. El defecto era invisible bajo
``--reuse-db`` (el schema arrastraba las tablas del árbol viejo). Se restituye
la creación real para que el grafo sea auto-contenido.
"""
import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalogue", "0001_initial"),
        ("orders", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    state_operations = [
        migrations.CreateModel(
            name="Review",
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
                (
                    "rating",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ]
                    ),
                ),
                ("title", models.CharField(max_length=120)),
                ("body", models.TextField(max_length=2000)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING_MODERATION", "Pendiente de moderación"),
                            ("APPROVED", "Aprobada"),
                            ("REJECTED", "Rechazada"),
                        ],
                        db_index=True,
                        default="PENDING_MODERATION",
                        max_length=22,
                    ),
                ),
                (
                    "reject_reason",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("CONTENIDO_INAPROPIADO", "Contenido inapropiado"),
                            ("SPAM", "Spam"),
                            ("LANGUAGE_NOT_SUPPORTED", "Idioma no soportado"),
                            ("NO_RELACIONADA", "No relacionada con el producto"),
                        ],
                        default="",
                        max_length=24,
                    ),
                ),
                ("moderated_at", models.DateTimeField(blank=True, null=True)),
                (
                    "helpful_count",
                    models.PositiveIntegerField(db_index=True, default=0),
                ),
                (
                    "moderated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="moderated_reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        help_text="Orden que prueba la compra (UC-REV-02).",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reviews",
                        to="orders.order",
                    ),
                ),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reviews",
                        to="catalogue.product",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reviews",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Reseña",
                "db_table": "reviews_review",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="ReviewHelpfulVote",
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
                    "review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="helpful_votes",
                        to="rating.review",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="helpful_votes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Voto util",
                "db_table": "reviews_helpful_vote",
            },
        ),
        migrations.CreateModel(
            name="ReviewImage",
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
                ("image", models.ImageField(upload_to="reviews/images/")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="images",
                        to="rating.review",
                    ),
                ),
            ],
            options={
                "db_table": "reviews_image",
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="ReviewModerationLog",
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
                    "action",
                    models.CharField(
                        choices=[("APPROVE", "Aprobar"), ("REJECT", "Rechazar")],
                        max_length=10,
                    ),
                ),
                ("reason", models.CharField(blank=True, default="", max_length=24)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "review",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="moderation_logs",
                        to="rating.review",
                    ),
                ),
            ],
            options={
                "verbose_name": "Auditoria de moderacion",
                "db_table": "reviews_moderation_log",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="review",
            constraint=models.UniqueConstraint(
                fields=("user", "product"), name="unique_review_user_product"
            ),
        ),
        migrations.AddConstraint(
            model_name="reviewhelpfulvote",
            constraint=models.UniqueConstraint(
                fields=("user", "review"), name="unique_helpful_vote_user_review"
            ),
        ),
    ]

    # H-API-21: las operaciones se aplican a la BD, no sólo al estado.
    operations = state_operations
