# Mueve MenuItem a la app addons.authz_menu (SOL-094 frente B, DEC-01).
# SeparateDatabaseAndState: la tabla ``authz_menu_item`` ya existe (creada por
# authz.0002); aqui solo se registra el modelo en el *state* de esta app. Sin
# database_operations => sin CREATE TABLE. El index conserva su nombre fisico
# (authz_menu__parent__8f655c_idx).

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("authz", "0012_remove_menuitem_authz_menu__parent__8f655c_idx_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.CreateModel(
            name="MenuItem",
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
                    "audience",
                    models.CharField(
                        choices=[
                            ("admin", "Panel admin"),
                            ("account", "Cuenta del comprador"),
                        ],
                        db_index=True,
                        default="admin",
                        help_text="'admin' = panel; 'account' = menú de cuenta del comprador.",
                        max_length=10,
                        verbose_name="Audiencia",
                    ),
                ),
                (
                    "key",
                    models.CharField(
                        help_text="Slug estable del item (para seed idempotente).",
                        max_length=80,
                        unique=True,
                        verbose_name="Clave",
                    ),
                ),
                ("label", models.CharField(max_length=80, verbose_name="Etiqueta")),
                (
                    "route",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="Ruta del router React (p.ej. '/admin/products'). Vacío en secciones.",
                        max_length=160,
                        verbose_name="Ruta SPA",
                    ),
                ),
                (
                    "icon",
                    models.CharField(
                        blank=True, default="", max_length=40, verbose_name="Icono"
                    ),
                ),
                ("order", models.PositiveIntegerField(default=0, verbose_name="Orden")),
                ("is_active", models.BooleanField(default=True, verbose_name="Activa")),
                (
                    "parent",
                    models.ForeignKey(
                        blank=True,
                        help_text="Null = sección de nivel 0.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="children",
                        to="authz_menu.menuitem",
                        verbose_name="Sección padre",
                    ),
                ),
                (
                    "required_capability",
                    models.ForeignKey(
                        blank=True,
                        help_text="Null = visible para cualquier admin (p.ej. secciones).",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="menu_items",
                        to="authz.capability",
                        verbose_name="Capacidad requerida",
                    ),
                ),
            ],
            options={
                "verbose_name": "Entrada de menú",
                "verbose_name_plural": "Entradas de menú",
                "db_table": "authz_menu_item",
                "ordering": ["parent_id", "order", "id"],
                "indexes": [
                    models.Index(
                        fields=["parent", "order"],
                        name="authz_menu__parent__8f655c_idx",
                    )
                ],
            },
                ),
            ],
        ),
    ]
