# ≙ account.journal hereda portal.mixin
# (odoo19c: addons/account/models/account_journal.py:46), que aporta la
# columna access_token
# (odoo19c: addons/portal/models/portal_mixin.py:16).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0050_payment_method_line_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountjournal",
            name="access_token",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text=(
                    "Token que permite el acceso al documento por link, "
                    "saltando los permisos del destinatario (Odoo "
                    "access_token)."
                ),
                max_length=64,
                verbose_name="Token de seguridad",
            ),
        ),
    ]
