"""Sprint 10 — StockMovement y StockAlert."""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('catalogue', '0005_productimage_admin_products'),
        ('chartsize', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StockMovement',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True)),
                ('delta',         models.IntegerField()),
                ('stock_after',   models.PositiveIntegerField()),
                ('movement_type', models.CharField(
                    max_length=20, db_index=True,
                    choices=[('SALE','Venta'),('CANCELLATION','Cancelacion'),
                             ('ADJUSTMENT','Ajuste manual'),('IMPORT','Importacion CSV')],
                )),
                ('reference',  models.CharField(blank=True, default='', max_length=50)),
                ('notes',      models.TextField(blank=True, default='')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('product',    models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_movements', to='catalogue.product',
                )),
                ('variant',    models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='stock_movements', to='chartsize.productvariant',
                )),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='stock_movements', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'inventory_stock_movement', 'ordering': ['-created_at']},
        ),
        migrations.CreateModel(
            name='StockAlert',
            fields=[
                ('id',             models.BigAutoField(auto_created=True, primary_key=True)),
                ('stock_at_alert', models.PositiveIntegerField()),
                ('resolved',       models.BooleanField(default=False, db_index=True)),
                ('resolved_at',    models.DateTimeField(blank=True, null=True)),
                ('created_at',     models.DateTimeField(auto_now_add=True, db_index=True)),
                ('product',    models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='stock_alerts', to='catalogue.product',
                )),
                ('variant',    models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='stock_alerts', to='chartsize.productvariant',
                )),
            ],
            options={'db_table': 'inventory_stock_alert', 'ordering': ['-created_at']},
        ),
    ]
