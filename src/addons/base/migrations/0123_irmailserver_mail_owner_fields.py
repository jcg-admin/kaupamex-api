"""Las columnas de dueño que ``mail`` añade a ``ir.mail_server``.

≙ ``odoo19c: addons/mail/models/ir_mail_server.py:20-32``. El modelo es de
``base``, así que sus columnas viven en las migraciones de ``base``; los
campos los declara ``addons/mail/models/ir_mail_server.py``.
"""

import django.db.models.deletion
import orm.table_objects
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0122_seed_derived_acl'),
    ]

    operations = [
        migrations.AddField(
            model_name='irmailserver',
            name='owner_limit_count',
            field=models.IntegerField(
                default=0, verbose_name='Owner Limit Count'),
        ),
        migrations.AddField(
            model_name='irmailserver',
            name='owner_limit_time',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Owner Limit Time'),
        ),
        migrations.AddField(
            model_name='irmailserver',
            name='owner_user_id',
            field=models.ForeignKey(
                blank=True, db_column='owner_user_id', null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='+', to=settings.AUTH_USER_MODEL,
                verbose_name='Owner'),
        ),
        migrations.AddConstraint(
            model_name='irmailserver',
            constraint=orm.table_objects.RawConstraint(
                'UNIQUE(owner_user_id)',
                name='ir_mail_server_unique_owner_user_id'),
        ),
    ]
