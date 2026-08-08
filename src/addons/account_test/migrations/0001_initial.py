from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="AccountingAssertTest",
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
                    "name",
                    models.CharField(
                        help_text="Nombre de la prueba (Odoo name, required, "
                        "translate).",
                        max_length=255,
                    ),
                ),
                (
                    "desc",
                    models.TextField(
                        blank=True,
                        default="",
                        help_text="Descripción de la prueba (Odoo desc, "
                        "translate).",
                    ),
                ),
                (
                    "code_exec",
                    models.TextField(
                        default="res = []\n"
                        "cr.execute(\"select id, code from account_journal\")\n"
                        "for record in cr.dictfetchall():\n"
                        "    res.append(record['code'])\n"
                        "result = res\n",
                        help_text="Código Python/SQL a ejecutar — DEBE fijar "
                        "la variable `result` (lista/dict) y opcionalmente "
                        "`column_order` (Odoo code_exec, required).",
                    ),
                ),
                (
                    "active",
                    models.BooleanField(
                        default=True,
                        help_text="Archivada sin borrar (Odoo active).",
                    ),
                ),
                (
                    "sequence",
                    models.IntegerField(
                        default=10,
                        help_text="Orden de presentación (Odoo sequence).",
                    ),
                ),
            ],
            options={
                "verbose_name": "Prueba de consistencia contable",
                "verbose_name_plural": "Pruebas de consistencia contable",
                "db_table": "account_test_accounting_assert_test",
                "ordering": ["sequence", "id"],
            },
        ),
    ]
