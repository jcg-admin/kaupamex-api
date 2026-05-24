from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    """
    H-CART-01: unique_together = [('cart', 'variant')] no protegía productos
    sin variante (NULL != NULL en SQL). Reemplazado por dos UniqueConstraints
    condicionales: uno para variantes, otro para productos sin variante.
    """

    dependencies = [
        ('cart', '0001_squashed_0005_remove_redundant_user_constraint'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='cartitem',
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name='cartitem',
            constraint=models.UniqueConstraint(
                condition=Q(variant__isnull=False),
                fields=['cart', 'variant'],
                name='unique_cart_variant',
            ),
        ),
        migrations.AddConstraint(
            model_name='cartitem',
            constraint=models.UniqueConstraint(
                condition=Q(variant__isnull=True),
                fields=['cart', 'product'],
                name='unique_cart_product_no_variant',
            ),
        ),
    ]
