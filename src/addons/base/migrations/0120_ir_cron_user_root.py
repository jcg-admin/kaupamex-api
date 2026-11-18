"""Los crons corren con su usuario; sin uno, el raíz — como la fuente.

≙ ``user_id`` obligatorio con ``default=lambda self: self.env.user``
(``odoo19c: odoo/addons/base/models/ir_cron.py:110``); los datos de una
instalación se cargan con ``SUPERUSER_ID``
(``odoo19c: odoo/modules/loading.py:404``), así que un cron sembrado queda
con ``base.user_root``. Aquí los crons sembrados quedaban con el usuario
nulo. Diseño: ``scripts/workbench/orm-continuation-plan-20261103T095630/
designs/ir-cron-user-root.md``.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import orm.environments


def fill_root_user(apps, schema_editor):
    """Asigna ``base.user_root`` a los crons sin usuario."""
    alias = schema_editor.connection.alias
    IrModelData = apps.get_model('base', 'IrModelData')
    IrCron = apps.get_model('base', 'IrCron')
    root = IrModelData.objects.using(alias).filter(
        module='base', name='user_root').values_list('res_id', flat=True)
    root_id = next(iter(root), None)
    if root_id is None:
        return
    IrCron.objects.using(alias).filter(user__isnull=True).update(
        user_id=root_id)


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0119_ir_exports_lines_copied'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(fill_root_user, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='ircron',
            name='user',
            field=models.ForeignKey(
                default=orm.environments.current_uid_or_superuser,
                help_text=(
                    'Usuario de ejecución (Odoo user_id, required, '
                    'default=env.user). Sin usuario actuante es el del '
                    'entorno que instala, SUPERUSER_ID, como en la '
                    'fuente. El runner lo aplica con '
                    'orm.environments.user_scope, así que '
                    'get_current_user() dentro del método invocado lo '
                    'devuelve. Caveat: IrRule.eval_context aún no cae a'
                    ' ese usuario — ver docstring del módulo.'
                ),
                on_delete=django.db.models.deletion.RESTRICT,
                related_name='ir_crons',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
