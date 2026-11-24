"""Los contactos de la regla de conciliación apuntan a ``res.partner``.

≙ ``partner_id``, ``mapped_partner_id`` y ``match_partner_ids`` con
``comodel_name='res.partner'``
(``odoo19c: addons/account/models/account_reconcile_model.py:20-23,
118-122, 144-145``). Los tres apuntaban al modelo de usuario; cada valor se
traduce al ``partner_id`` del usuario, que es el contacto que la fuente
le hereda por ``_inherits``. Un usuario que ya no exista deja la Many2one
en NULL y su fila de la Many2many fuera, lo mismo que ``SET_NULL``.
"""

import django.db.models.deletion
from django.db import migrations, models

FORWARD_SQL = """
UPDATE account_reconcile_model_line AS line
   SET partner_id = u.partner_id
  FROM res_users AS u
 WHERE u.id = line.partner_user_legacy_id;

UPDATE account_reconcile_model AS rule
   SET mapped_partner_id = u.partner_id
  FROM res_users AS u
 WHERE u.id = rule.mapped_partner_user_legacy_id;

INSERT INTO account_reconcile_model_match_partner_ids
       (accountreconcilemodel_id, respartner_id)
SELECT DISTINCT legacy.accountreconcilemodel_id, u.partner_id
  FROM account_reconcile_model_match_partner_user_legacy_ids AS legacy
  JOIN res_users AS u ON u.id = legacy.resusers_id
 WHERE u.partner_id IS NOT NULL;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0053_report_line_code_null"),
    ]

    operations = [
        migrations.RenameField(
            model_name="accountreconcilemodelline",
            old_name="partner",
            new_name="partner_user_legacy",
        ),
        migrations.RenameField(
            model_name="accountreconcilemodel",
            old_name="mapped_partner",
            new_name="mapped_partner_user_legacy",
        ),
        migrations.RenameField(
            model_name="accountreconcilemodel",
            old_name="match_partner_ids",
            new_name="match_partner_user_legacy_ids",
        ),
        migrations.AddField(
            model_name="accountreconcilemodelline",
            name="partner",
            field=models.ForeignKey(
                blank=True,
                help_text="Contacto de la línea generada (Odoo partner_id).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="base.respartner",
            ),
        ),
        migrations.AddField(
            model_name="accountreconcilemodel",
            name="mapped_partner",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Odoo mapped_partner_id (computado, ver "
                    "compute_mapped_partner_id)."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="base.respartner",
            ),
        ),
        migrations.AddField(
            model_name="accountreconcilemodel",
            name="match_partner_ids",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "Restringe la regla a estos contactos (Odoo "
                    "match_partner_ids)."
                ),
                related_name="+",
                to="base.respartner",
            ),
        ),
        migrations.RunSQL(FORWARD_SQL, migrations.RunSQL.noop),
        migrations.RemoveField(
            model_name="accountreconcilemodelline",
            name="partner_user_legacy",
        ),
        migrations.RemoveField(
            model_name="accountreconcilemodel",
            name="mapped_partner_user_legacy",
        ),
        migrations.RemoveField(
            model_name="accountreconcilemodel",
            name="match_partner_user_legacy_ids",
        ),
    ]
