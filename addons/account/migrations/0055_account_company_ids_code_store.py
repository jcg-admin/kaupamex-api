"""La cuenta gana ``company_ids`` y ``code_store``, junto a sus columnas.

≙ ``company_ids`` y ``code_store = fields.Char(company_dependent=True)``
(``odoo19c: addons/account/models/account_account.py:40, 97-99``). Primer
paso del porte multiempresa (``designs/account-account-multicompany-code.md``,
MC1): ``company`` y ``code`` siguen siendo columnas, y aquí se copian a las
nuevas. ``code_store`` guarda el código bajo la empresa raíz de la
compañía, que es la que la fuente usa para leer ``code``.
"""

import orm.fields_company_dependent
from django.db import migrations, models

FORWARD_SQL = """
INSERT INTO account_account_res_company_rel (accountaccount_id, rescompany_id)
SELECT account.id, account.company_id
  FROM account_account AS account
 WHERE account.company_id IS NOT NULL
ON CONFLICT DO NOTHING;

UPDATE account_account AS account
   SET code_store = jsonb_build_object(
           COALESCE(NULLIF(split_part(company.parent_path, '/', 1), ''),
                    company.id::text),
           account.code)
  FROM res_company AS company
 WHERE company.id = account.company_id
   AND COALESCE(account.code, '') <> '';
"""


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0054_reconcile_partner_comodel"),
        ("base", "0128_rewrite_model_identities"),
    ]

    operations = [
        migrations.AddField(
            model_name="accountaccount",
            name="code_store",
            field=orm.fields_company_dependent.CompanyDependent(
                blank=True,
                default=dict,
                help_text="Código por empresa raíz (Odoo code_store).",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="accountaccount",
            name="company_ids",
            field=models.ManyToManyField(
                blank=True,
                db_table="account_account_res_company_rel",
                help_text="Empresas de la cuenta (Odoo company_ids).",
                related_name="+",
                to="base.rescompany",
            ),
        ),
        migrations.AddIndex(
            model_name="accountaccount",
            index=models.Index(
                models.ExpressionWrapper(
                    models.Q(("code_store__isnull", False)),
                    output_field=models.BooleanField(),
                ),
                condition=models.Q(("code_store__isnull", False)),
                name="account_account__code_e74b1b77",
            ),
        ),
        migrations.RunSQL(FORWARD_SQL, migrations.RunSQL.noop),
    ]
