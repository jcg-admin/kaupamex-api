"""La cuenta pierde la columna ``code``: el código vive en ``code_store``.

≙ ``code`` calculado sobre ``code_store`` en la raíz de la empresa activa
(``odoo19c: addons/account/models/account_account.py:39-40, 333-353``).
MC2c-1 de ``designs/account-account-mc2c.md``. Antes de retirar la columna
se copia a ``code_store`` el código de las filas que todavía no lo tengan en
la raíz de su empresa (MC1 lo replica al guardar y 0055 al migrar; esta
copia cubre lo que se haya escrito sin pasar por ninguno de los dos).
"""

from django.db import migrations

FORWARD_SQL = """
UPDATE account_account AS account
   SET code_store = COALESCE(account.code_store, '{}'::jsonb)
       || jsonb_build_object(
              COALESCE(NULLIF(split_part(company.parent_path, '/', 1), ''),
                       company.id::text),
              account.code)
  FROM res_company AS company
 WHERE company.id = account.company_id
   AND COALESCE(account.code, '') <> ''
   AND NOT COALESCE(account.code_store, '{}'::jsonb) ?
       COALESCE(NULLIF(split_part(company.parent_path, '/', 1), ''),
                company.id::text);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('account', '0055_account_company_ids_code_store'),
    ]

    operations = [
        migrations.RunSQL(FORWARD_SQL, migrations.RunSQL.noop),
        migrations.AlterModelOptions(
            name='accountaccount',
            options={
                'ordering': ['id'],
                'verbose_name': 'Cuenta contable',
                'verbose_name_plural': 'Cuentas contables',
            },
        ),
        migrations.RemoveConstraint(
            model_name='accountaccount',
            name='unique_account_code_company',
        ),
        migrations.RemoveField(
            model_name='accountaccount',
            name='code',
        ),
    ]
