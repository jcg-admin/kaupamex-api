"""
Migración de infraestructura: herencia-modelos-django — apps.inventory
ADD updated_at en StockMovement y StockAlert.
created_at ya existe con db_index=True (DEC-003 — override en modelo).
"""
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('inventory', '0001_initial')]
    operations = [
        migrations.AddField(model_name='stockmovement', name='updated_at',
            field=models.DateTimeField(auto_now=True)),
        migrations.AddField(model_name='stockalert', name='updated_at',
            field=models.DateTimeField(auto_now=True)),
    ]
