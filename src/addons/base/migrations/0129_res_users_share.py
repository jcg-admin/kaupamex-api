"""``res.users.share`` — columna y valores.

≙ ``odoo19c: odoo/addons/base/models/res_users.py:234-235,459-464``: un
booleano almacenado y calculado de ``all_group_ids``. Las filas existentes lo
reciben de ``ComputeStoredFields`` con su ``_compute_share``, como
``_auto_init`` calcula una columna almacenada nueva
(``designs/base-res-users-share-field-0356.md``).
"""

from django.db import migrations, models

from orm.migration_operations import ComputeStoredFields


class Migration(migrations.Migration):

    dependencies = [
        ("base", "0128_rewrite_model_identities"),
    ]

    operations = [
        migrations.AddField(
            model_name="resusers",
            name="share",
            field=models.BooleanField(
                default=True,
                editable=False,
                help_text="External user with limited access, created only "
                "for the purpose of sharing data.",
                verbose_name="Share User",
            ),
        ),
        ComputeStoredFields("base", "resusers", ["share"]),
    ]
