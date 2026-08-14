"""Las cuatro fechas de caducidad y el recordatorio, sobre ``stock.lot``.

Las declara ``product_expiry`` con ``add_to_class``
(≙ ``odoo19c: product_expiry/models/production_lot.py:13-27``), pero la
columna pertenece a ``stock``, que es el dueño del modelo — mismo criterio que
``product/migrations/0005_expiry_and_tracking_surface.py``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='stocklot',
            name='expiration_date',
            field=models.DateTimeField(
                null=True, blank=True,
                help_text='Fecha en que el lote deja de ser consumible '
                          '(Odoo expiration_date).',
            ),
        ),
        migrations.AddField(
            model_name='stocklot',
            name='use_date',
            field=models.DateTimeField(
                null=True, blank=True,
                help_text='Fecha desde la que el producto empieza a deteriorarse — '
                          'consumo preferente (Odoo use_date).',
            ),
        ),
        migrations.AddField(
            model_name='stocklot',
            name='removal_date',
            field=models.DateTimeField(
                null=True, blank=True,
                help_text='Fecha en que el lote debe retirarse del stock; clave del '
                          'orden FEFO (Odoo removal_date).',
            ),
        ),
        migrations.AddField(
            model_name='stocklot',
            name='alert_date',
            field=models.DateTimeField(
                null=True, blank=True,
                help_text='Fecha en que se levanta la alerta de caducidad '
                          '(Odoo alert_date).',
            ),
        ),
        migrations.AddField(
            model_name='stocklot',
            name='product_expiry_reminded',
            field=models.BooleanField(
                default=False,
                help_text='La alerta de caducidad ya se notificó '
                          '(Odoo product_expiry_reminded).',
            ),
        ),
    ]
