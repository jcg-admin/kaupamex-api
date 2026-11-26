"""El dueño de ``res.users.log`` vuelve a ``create_uid``.

≙ ``odoo19c: odoo/addons/base/models/res_users.py:134-152,231``: la fuente
guarda el acceso sólo en ``create_uid`` (indexado, con el inverso
``log_ids``). La FK ``user`` se copia a ``create_uid`` y se retira; después
se siembran la ACL de ``group_system`` y la regla por usuario
(``ir.model.access.csv:89``, ``base_security.xml:5-10``). Diseño:
``designs/basemodel-adoption-res-users-log.md``.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

from addons.base.security.base_security import seed_base_rules
from addons.base.security.ir_model_access import seed_base_acl


def copy_owner(apps, schema_editor):
    """``user_id`` a ``create_uid`` en cada fila."""
    log = apps.get_model('base', 'ResUsersLog')
    log.objects.using(schema_editor.connection.alias).update(
        create_uid=models.F('user'))


def seed(apps, schema_editor):
    alias = schema_editor.connection.alias
    seed_base_acl(apps, alias)
    seed_base_rules(apps, alias)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0137_seed_cron_res_users_deletion'),
    ]

    operations = [
        migrations.AlterField(
            model_name='resuserslog',
            name='create_uid',
            field=models.ForeignKey(
                blank=True,
                db_column='create_uid',
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='log_ids',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Created by',
            ),
        ),
        # Sin marcha atrás: la FK ``user`` no se reconstruye.
        migrations.RunPython(copy_owner, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='resuserslog',
            name='user',
        ),
        # Sin marcha atrás, mismo criterio que ``0059`` y ``0122``.
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]
