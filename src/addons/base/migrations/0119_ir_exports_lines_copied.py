"""``ir.exports``: las líneas se declaran y se copian, como en la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_exports.py:7-23``.
``export_fields`` pasa a ser un ``One2many(copy=True)`` declarado en el
padre, así que la FK del hijo se llama ``export_id`` (su columna de siempre)
y lleva ``related_name='+'``. Con ``_name`` declarado, ``ir.exports.line``
recibe las cuatro columnas de auditoría que la fuente da a todo modelo con
``_log_access``; las filas existentes toman la hora de la migración, como en
``0110_log_access_auto_injection``.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def _log_user(name):
    return migrations.AddField(
        model_name='irexportsline',
        name=name,
        field=models.ForeignKey(
            blank=True,
            db_column=name,
            db_index=False,
            editable=False,
            null=True,
            on_delete=django.db.models.deletion.SET_NULL,
            related_name='+',
            to=settings.AUTH_USER_MODEL,
        ),
    )


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0118_set_null_ondelete_block_d'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # La columna ya se llama ``export_id``: sólo cambia el estado.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RenameField(
                    model_name='irexportsline',
                    old_name='export',
                    new_name='export_id',
                ),
                migrations.AlterField(
                    model_name='irexportsline',
                    name='export_id',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='export_id',
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='+',
                        to='base.irexports',
                        verbose_name='Exportación',
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name='irexportsline',
            name='create_date',
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
            ),
            preserve_default=False,
        ),
        _log_user('create_uid'),
        migrations.AddField(
            model_name='irexportsline',
            name='write_date',
            field=models.DateTimeField(auto_now=True),
        ),
        _log_user('write_uid'),
    ]
