"""Columnas del log-access para ``account.analytic.account``.

La clase heredaba ``_name = 'mail.thread'`` de ``MailThread`` y la
inyección del log-access (DEC-09) no la alcanzaba. Con la cabecera de la
fuente (``odoo19c: addons/analytic/models/analytic_account.py:11-18``)
recibe las cuatro columnas que la metaclase añade a todo modelo
(``odoo19c: odoo/orm/models.py:287-292``), con los nombres de la fuente.
Las filas existentes reciben la fecha de la migración.
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def _user_column(column):
    return models.ForeignKey(
        blank=True,
        db_column=column,
        db_index=False,
        editable=False,
        null=True,
        on_delete=django.db.models.deletion.SET_NULL,
        related_name='+',
        to=settings.AUTH_USER_MODEL,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('analytic', '0010_log_access_user_column_names'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='accountanalyticaccount',
            name='create_date',
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='accountanalyticaccount',
            name='write_date',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='accountanalyticaccount',
            name='create_uid',
            field=_user_column('create_uid'),
        ),
        migrations.AddField(
            model_name='accountanalyticaccount',
            name='write_uid',
            field=_user_column('write_uid'),
        ),
    ]
