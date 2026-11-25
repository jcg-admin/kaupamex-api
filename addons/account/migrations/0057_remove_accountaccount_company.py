"""La cuenta deja la columna ``company``: su empresa es ``company_ids``.

≙ ``company_ids``
(``odoo19c: addons/account/models/account_account.py:97-99``), que es la
única relación de empresa de ``account.account`` en la fuente.
``0055`` copió ``company`` a ``account_account_res_company_rel`` y desde MC1
``save`` mantuvo las dos al día, así que retirar la columna no pierde datos
(``designs/account-account-mc2c.md``, MC2c-2).

Reversible: al revertir, la columna vuelve nula, se rellena con la primera
empresa de ``company_ids`` de cada cuenta y sólo entonces recupera su
``NOT NULL``.
"""

import django.db.models.deletion
from django.db import migrations, models

BACKFILL_SQL = """
UPDATE account_account AS account
   SET company_id = rel.first_company_id
  FROM (SELECT accountaccount_id, MIN(rescompany_id) AS first_company_id
          FROM account_account_res_company_rel
         GROUP BY accountaccount_id) AS rel
 WHERE rel.accountaccount_id = account.id;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0056_account_code_over_code_store"),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountaccount",
            name="company",
            field=models.ForeignKey(
                help_text="Empresa (Odoo company_id / company_ids).",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="accounts",
                to="base.rescompany",
            ),
        ),
        migrations.RunSQL(migrations.RunSQL.noop, reverse_sql=BACKFILL_SQL),
        migrations.RemoveField(
            model_name="accountaccount",
            name="company",
        ),
    ]
