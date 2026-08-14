"""Las columnas que ``product_expiry`` y ``stock`` cuelgan de ``product.template``.

Django exige que la migración de una columna viva en la app **dueña** del
modelo, aunque el campo lo declare otro addon con ``add_to_class``. Mismo
criterio que ``base/migrations/0015_resbank_l10n_mx_edi_code_and_more.py`` para
los campos que ``l10n_mx`` cuelga sobre ``res.partner.bank``.

- Los cinco de caducidad ≙ ``odoo19c: product_expiry/models/product_product.py:20-34``.
- ``tracking`` ≙ ``odoo19c: stock/models/product.py:842-848``.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('product', '0004_alter_producttemplate_supplier_taxes_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='producttemplate',
            name='use_expiration_date',
            field=models.BooleanField(
                default=False,
                help_text='Gestiona fechas de caducidad (Odoo use_expiration_date).',
            ),
        ),
        migrations.AddField(
            model_name='producttemplate',
            name='expiration_time',
            field=models.IntegerField(
                default=0,
                help_text='Días tras la recepción hasta la caducidad del lote '
                          '(Odoo expiration_time).',
            ),
        ),
        migrations.AddField(
            model_name='producttemplate',
            name='use_time',
            field=models.IntegerField(
                default=0,
                help_text='Días antes de la caducidad en que el producto empieza a '
                          'deteriorarse — consumo preferente (Odoo use_time).',
            ),
        ),
        migrations.AddField(
            model_name='producttemplate',
            name='removal_time',
            field=models.IntegerField(
                default=0,
                help_text='Días antes de la caducidad para retirar del stock '
                          '(Odoo removal_time).',
            ),
        ),
        migrations.AddField(
            model_name='producttemplate',
            name='alert_time',
            field=models.IntegerField(
                default=0,
                help_text='Días antes de la caducidad para levantar una alerta '
                          '(Odoo alert_time).',
            ),
        ),
        migrations.AddField(
            model_name='producttemplate',
            name='tracking',
            field=models.CharField(
                choices=[
                    ('serial', 'Por número de serie único'),
                    ('lot', 'Por lotes'),
                    ('none', 'Por cantidad'),
                ],
                default='none', max_length=16,
                help_text='Trazabilidad del producto almacenable (Odoo tracking).',
            ),
        ),
    ]
