"""
Migración de infraestructura: herencia-modelos-django — apps.orders
ADD created_at + updated_at en OrderItem, OrderValue, OrderAddress.
Order: refactor puro (ya tenía ambos campos con db_index en created_at).
"""
import django.utils.timezone
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('orders', '0001_initial')]
    operations = [
        migrations.AddField(model_name='orderitem', name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False),
        migrations.AddField(model_name='orderitem', name='updated_at',
            field=models.DateTimeField(auto_now=True)),
        migrations.AddField(model_name='ordervalue', name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False),
        migrations.AddField(model_name='ordervalue', name='updated_at',
            field=models.DateTimeField(auto_now=True)),
        migrations.AddField(model_name='orderaddress', name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False),
        migrations.AddField(model_name='orderaddress', name='updated_at',
            field=models.DateTimeField(auto_now=True)),
    ]
