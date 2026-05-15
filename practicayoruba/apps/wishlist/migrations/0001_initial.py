"""Sprint 14 — WishlistItem."""
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
            name='WishlistItem',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True)),
                ('price_at_add', models.DecimalField(decimal_places=2, max_digits=10)),
                ('created_at',   models.DateTimeField(auto_now_add=True)),
                ('user',    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                related_name='wishlist_items', to=settings.AUTH_USER_MODEL)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                related_name='wishlist_items', to='catalogue.product')),
                ('variant', models.ForeignKey(blank=True, null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name='wishlist_items', to='chartsize.productvariant')),
            ],
            options={'db_table': 'wishlist_item', 'ordering': ['-created_at']},
        ),
        migrations.AddConstraint(
            model_name='wishlistitem',
            constraint=models.UniqueConstraint(
                fields=['user', 'product', 'variant'], name='unique_user_product_variant'
            ),
        ),
    ]
