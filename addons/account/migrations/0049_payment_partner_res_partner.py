# ≙ account.payment partner_id
# (odoo19c: addons/account/models/account_payment.py:116): res.partner con
# ondelete='restrict'. Aquí apuntaba al usuario con SET_NULL.
#
# El valor guardado es un id de usuario, así que la restricción no puede
# cambiar de tabla con esos valores dentro: primero se suelta, luego cada
# id de usuario se sustituye por el partner de ese usuario, y al final se
# crea la restricción contra res_partner, con ON DELETE RESTRICT.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def users_to_partners(apps, schema_editor):
    """Cada pago que apuntaba a un usuario pasa a apuntar a su partner."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'UPDATE account_payment AS payment '
            'SET partner_id = users.partner_id '
            'FROM res_users AS users '
            'WHERE payment.partner_id = users.id')


class Migration(migrations.Migration):

    dependencies = [
        ("account", "0048_payment_date_name"),
        ("base", "0118_set_null_ondelete_block_d"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="accountpayment",
            name="partner",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                help_text="Contacto (Odoo partner_id → party).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="account_payments",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(users_to_partners, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="accountpayment",
            name="partner",
            field=models.ForeignKey(
                blank=True,
                help_text="Cliente o proveedor (Odoo partner_id).",
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="account_payments",
                to="base.respartner",
            ),
        ),
    ]
