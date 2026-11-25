"""El modelo virtual ``account.code.mapping`` entra en el estado de Django.

≙ ``odoo19c: addons/account/models/account_code_mapping.py:14-17``
(``_auto = False``, ``_table_query = '0'``): sin tabla. ``managed = False``
hace que esta migración no cree nada en la base; sólo registra el modelo
(``designs/account-code-mapping.md``).
"""

import orm.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0057_remove_accountaccount_company"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccountCodeMapping",
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
            ],
            options={
                "db_table": "account_code_mapping",
                "managed": False,
            },
            bases=(
                orm.models.DefaultGetMixin,
                orm.models.RecordLoaderMixin,
                orm.models.OrderMixin,
                orm.models.CheckCompanyMixin,
                models.Model,
            ),
        ),
    ]
