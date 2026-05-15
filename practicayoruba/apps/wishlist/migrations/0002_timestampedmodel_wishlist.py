"""
Migración de infraestructura: herencia-modelos-django — apps.wishlist
ADD updated_at en WishlistItem (ya tenía created_at).
"""
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('wishlist', '0001_initial')]
    operations = [
        migrations.AddField(model_name='wishlistitem', name='updated_at',
            field=models.DateTimeField(auto_now=True)),
    ]
