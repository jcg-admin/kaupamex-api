"""Sprint 12 — Cart, CartItem, SavedCart, SavedCartItem."""
import uuid
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.core.validators
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
            name='Cart',
            fields=[
                ('id',         models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True)),
                ('cart_token', models.UUIDField(blank=True, db_index=True, null=True, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user',       models.OneToOneField(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='cart', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'cart_cart', 'verbose_name': 'Carrito'},
        ),
        migrations.AddConstraint(
            model_name='cart',
            constraint=models.UniqueConstraint(
                condition=models.Q(user__isnull=False),
                fields=['user'], name='unique_user_cart',
            ),
        ),
        migrations.CreateModel(
            name='CartItem',
            fields=[
                ('id',         models.BigAutoField(auto_created=True, primary_key=True)),
                ('quantity',   models.PositiveIntegerField(
                    default=1,
                    validators=[django.core.validators.MinValueValidator(1)],
                )),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('cart',       models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items', to='cart.cart',
                )),
                ('product',    models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='cart_items', to='catalogue.product',
                )),
                ('variant',    models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='cart_items', to='chartsize.productvariant',
                )),
            ],
            options={'db_table': 'cart_cart_item', 'verbose_name': 'Item de carrito'},
        ),
        migrations.AddConstraint(
            model_name='cartitem',
            constraint=models.UniqueConstraint(
                fields=['cart', 'variant'], name='unique_cart_variant'
            ),
        ),
        migrations.CreateModel(
            name='SavedCart',
            fields=[
                ('id',       models.BigAutoField(auto_created=True, primary_key=True)),
                ('saved_at', models.DateTimeField(auto_now=True)),
                ('user',     models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saved_cart', to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={'db_table': 'cart_saved_cart'},
        ),
        migrations.CreateModel(
            name='SavedCartItem',
            fields=[
                ('id',            models.BigAutoField(auto_created=True, primary_key=True)),
                ('quantity',      models.PositiveIntegerField(default=1)),
                ('price_at_save', models.DecimalField(decimal_places=2, max_digits=10)),
                ('saved_cart',    models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='items', to='cart.savedcart',
                )),
                ('product',       models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='catalogue.product',
                )),
            ],
            options={'db_table': 'cart_saved_cart_item'},
        ),
        migrations.AddConstraint(
            model_name='savedcartitem',
            constraint=models.UniqueConstraint(
                fields=['saved_cart', 'product'], name='unique_saved_cart_product'
            ),
        ),
    ]
