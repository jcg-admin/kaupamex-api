"""Siembra el cron ``ir_cron_res_users_deletion``.

≙ ``odoo19c: odoo/addons/base/data/ir_cron_data.xml:13-21``: una vez al
día, prioridad 8, ``model._gc_portal_users(batch_size=50)`` sobre
``res.users.deletion`` (``designs/basemodel-adoption-res-users-deletion.md``).
La siembra es idempotente.
"""

from django.db import migrations

from addons.base.data import CRON_RES_USERS_DELETION, sembrar_cron


def seed(apps, schema_editor):
    sembrar_cron(apps, schema_editor.connection.alias,
                 CRON_RES_USERS_DELETION)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0136_seed_res_users_deletion_access'),
    ]

    operations = [
        # Sin marcha atrás, mismo criterio que ``0059`` y ``0122``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
