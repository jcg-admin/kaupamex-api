"""Adopta ``SearchEntry`` (historial de búsqueda) en ``website``.

State-only (``SeparateDatabaseAndState``): la tabla ``search_history_entry`` ya
existe (creada por ``search_history.0001_initial``); la telemetría de búsqueda
por usuario se re-aloja en ``website`` porque en Odoo el rastreo de
comportamiento del visitante del storefront vive en ``website``
(``website.visitor``/``website.track``). Sólo cambia el ``app_label`` — sin DDL.
La contraparte ``search_history.0002_delete_searchentry`` lo retira del estado
de ``search_history``.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("website", "0002_staticpage_banner_staticpageversion"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    state_operations = [
        migrations.CreateModel(
            name="SearchEntry",
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
                ("query", models.CharField(max_length=200)),
                ("normalized_query", models.CharField(db_index=True, max_length=200)),
                ("results_count", models.PositiveIntegerField(default=0)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="search_entries",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Entrada de historial de busqueda",
                "db_table": "search_history_entry",
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
