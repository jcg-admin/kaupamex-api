"""Los hilos de los nueve modelos que declararon su nombre cambian de clave.

``_mail_thread_res_model`` y ``_activity_res_model`` devuelven el ``_name``
propio del modelo y, sin él, su label de Django. Nueve modelos heredaban el
de un mixin y se guardaban por label; ahora declaran el suyo
(designs/analytic-account-header.md), así que los mensajes, seguidores y
actividades ya guardados se traducen a la nueva clave para que las consultas
por ``(model, res_id)`` los sigan encontrando. Reversible.
"""
from django.db import migrations

#: label de Django → ``_name`` declarado.
RENAMED = {
    'base_automation.BaseAutomation': 'base.automation',
    'fleet.FleetVehicleModel': 'fleet.vehicle.model',
    'fleet.FleetVehicle': 'fleet.vehicle',
    'fleet.FleetVehicleLogContract': 'fleet.vehicle.log.contract',
    'fleet.FleetVehicleLogServices': 'fleet.vehicle.log.services',
    'mass_mailing.MailingMailing': 'mailing.mailing',
    'website.StaticPage': 'settings.static.page',
    'stock.ReturnRequest': 'return.request',
    'helpdesk.SupportTicket': 'support.ticket',
}

#: tabla → columna que guarda la clave del modelo.
COLUMNS = {
    'mail_message': 'model',
    'mail_followers': 'res_model',
    'mail_activity': 'res_model',
}


def _translate(schema_editor, mapping):
    with schema_editor.connection.cursor() as cursor:
        for table, column in COLUMNS.items():
            for old, new in mapping.items():
                cursor.execute(
                    f'UPDATE {table} SET {column} = %s WHERE {column} = %s',
                    [new, old])


def forwards(apps, schema_editor):
    _translate(schema_editor, RENAMED)


def backwards(apps, schema_editor):
    _translate(schema_editor, {new: old for old, new in RENAMED.items()})


class Migration(migrations.Migration):

    dependencies = [
        ('mail', '0008_log_access_user_column_names'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
