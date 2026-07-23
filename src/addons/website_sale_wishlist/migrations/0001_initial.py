"""Adopta ``WishlistItem`` en ``website_sale_wishlist`` (hogar fiel Odoo).

State-only (``SeparateDatabaseAndState``): la tabla ``wishlist_item`` ya existe
(creada por la ex-migración ``wishlist.0001_initial``); la lista de deseos se
re-aloja en ``website_sale_wishlist`` porque en Odoo la wishlist del storefront
la provee ese módulo (``product.wishlist``), no un módulo ``wishlist`` a secas.
Sólo cambia el ``app_label`` del modelo — sin DDL. La contraparte
``wishlist.0002_delete_wishlistitem`` lo retira del estado de ``wishlist``.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("catalogue", "0001_initial"),
        ("chartsize", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    state_operations = [
        migrations.CreateModel(
            name="WishlistItem",
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
                ("price_at_add", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wishlist_items",
                        to="catalogue.product",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="wishlist_items",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "variant",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wishlist_items",
                        to="chartsize.productvariant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Item de lista de deseos",
                "db_table": "wishlist_item",
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("variant__isnull", False)),
                        fields=("user", "product", "variant"),
                        name="unique_wishlist_user_product_variant",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("variant__isnull", True)),
                        fields=("user", "product"),
                        name="unique_wishlist_user_product_no_variant",
                    ),
                ],
            },
        ),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=state_operations,
            database_operations=[],
        ),
    ]
