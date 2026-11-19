"""``mailing.subscription.list_id`` con el nombre de la fuente.

≙ ``list_id`` (``odoo19c: addons/mass_mailing/models/
mailing_subscription.py:18``). Se renombra campo y columna para conservar las
filas; la restricción única se rehace sobre el nombre nuevo.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('mass_mailing', '0005_log_access_user_column_names'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='mailingsubscription',
            name='unique_mailing_subscription',
        ),
        migrations.RenameField(
            model_name='mailingsubscription',
            old_name='mailing_list',
            new_name='list_id',
        ),
        migrations.AlterField(
            model_name='mailingsubscription',
            name='list_id',
            field=models.ForeignKey(
                db_column='list_id', help_text='Lista (Odoo list_id).',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='subscription_ids',
                to='mass_mailing.mailinglist'),
        ),
        migrations.AddConstraint(
            model_name='mailingsubscription',
            constraint=models.UniqueConstraint(
                fields=('contact_id', 'list_id'),
                name='unique_mailing_subscription'),
        ),
    ]
