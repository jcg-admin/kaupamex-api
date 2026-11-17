# ≙ los xmlid mail.mt_comment y mail.mt_note (odoo19c:
# addons/mail/data/mail_message_subtype_data.xml:5,10). La 0002 sembró los
# subtipos sin su fila de ir.model.data; esta la graba sobre los existentes.

from django.db import migrations

from addons.mail.data import register_subtype_xmlids


def register(apps, schema_editor):
    register_subtype_xmlids(
        apps.get_model('mail', 'MailMessageSubtype'),
        apps.get_model('base', 'IrModelData'),
        schema_editor.connection.alias)


class Migration(migrations.Migration):

    dependencies = [
        ("mail", "0009_thread_models_own_names"),
        ("base", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(register, migrations.RunPython.noop),
    ]
