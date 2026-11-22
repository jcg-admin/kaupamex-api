"""Rellena el ``code`` de las acciones de cron que lo tienen vacío.

Desde ``cron-runs-server-action-0397`` el cron ejecuta su acción con
``run()``, como la fuente
(``odoo19c: odoo/addons/base/models/ir_cron.py:688``);
una acción sembrada antes lleva ``code=''`` y no haría nada. Se le escribe
``model.<method_name>()``, la llamada que el corredor de métodos hacía.
"""
from django.db import DEFAULT_DB_ALIAS, migrations


def fill_code(apps, schema_editor):
    alias = (schema_editor.connection.alias if schema_editor is not None
             else DEFAULT_DB_ALIAS)
    IrActionsServer = apps.get_model('base', 'IrActionsServer')
    actions = IrActionsServer.objects.using(alias).filter(
        state='code', code='').exclude(method_name='')
    for action in actions:
        action.code = f'model.{action.method_name}()'
        action.save(update_fields=['code'])


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0125_irattachment_res_id_help_text'),
    ]

    operations = [
        migrations.RunPython(fill_code, migrations.RunPython.noop),
    ]
