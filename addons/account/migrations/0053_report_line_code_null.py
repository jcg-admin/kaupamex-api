"""El código de una línea de informe vuelve a ser NULL cuando falta.

≙ ``code = fields.Char(...)`` sin valor por defecto y ``_code_uniq``
(``odoo19c: addons/account/models/account_report.py:386, 398-401``): la
fuente guarda NULL y la restricción única no compara dos NULL. Las filas
que guardaban ``''`` pasan a NULL después de permitirlo.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0052_accountjournal_edi_format_ids"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountreportline",
            name="code",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Identificador único de la línea dentro del reporte; lo"
                    " usan las fórmulas de agregación para referirse a ella"
                    " (Odoo code)."
                ),
                max_length=64,
                null=True,
            ),
        ),
        migrations.RunSQL(
            "UPDATE account_report_line SET code = NULL WHERE code = '';",
            migrations.RunSQL.noop,
        ),
    ]
