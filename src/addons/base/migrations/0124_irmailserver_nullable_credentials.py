"""``smtp_user`` y ``smtp_pass`` vuelven a ser nulables, como en la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_mail_server.py:169-170``: dos
``fields.Char`` sin ``required`` ni ``default``, así que ``False`` se guarda
como ``NULL``. ``action_setup_outgoing_mail_server`` de ``mail`` crea el
servidor personal con ``smtp_pass = False`` (``odoo19c:
addons/mail/models/res_users.py:617-627``); con la columna ``NOT NULL`` la
inserción fallaba.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0123_irmailserver_mail_owner_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='irmailserver',
            name='smtp_pass',
            field=models.CharField(
                blank=True,
                help_text=(
                    'SECRETO. Mismo criterio que smtp_user: nunca en un '
                    'serializer.'),
                max_length=255, null=True, verbose_name='Contraseña'),
        ),
        migrations.AlterField(
            model_name='irmailserver',
            name='smtp_user',
            field=models.CharField(
                blank=True,
                help_text=(
                    'SECRETO. La referencia lo restringe a nivel de campo con '
                    'groups="base.group_system"; aquí NO se expone en el '
                    'Meta.fields de ningún serializer.'),
                max_length=255, null=True, verbose_name='Usuario'),
        ),
    ]
