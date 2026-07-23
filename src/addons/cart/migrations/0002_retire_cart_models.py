"""S4 unificación cart→order→sale (analisis-unificar-cart-order-sale).

En Odoo el carrito ES un ``sale.order`` en ``state='draft'`` — no una tabla
aparte. Esta migración cierra el strangler del carrito:

1. **Data port**: cada fila viva de ``Cart`` se convierte en un
   ``orders.Order(status=DRAFT)`` con sus ``OrderItem`` (snapshot desde el
   producto/variante, como hacen los servicios del draft). El voucher se
   porta como ``voucher_code`` (el draft recalcula el descuento vivo).
2. **Drop**: se eliminan los modelos y tablas ``cart_cart`` y
   ``cart_cart_item``. ``SavedCart``/``SavedCartItem`` (UC-CART-05)
   permanecen en este addon.

Los modelos históricos no ejecutan ``save()`` custom, así que el
``order_number`` se acuña aquí (prefijo ``PY-MIG``) para las filas portadas.
"""
import uuid

from django.db import migrations


def _port_carts_to_drafts(apps, schema_editor):
    Cart = apps.get_model('cart', 'Cart')
    Order = apps.get_model('orders', 'Order')
    OrderItem = apps.get_model('orders', 'OrderItem')

    for cart in Cart.objects.select_related('voucher').all():
        items = list(cart.items.select_related('product', 'variant').all())
        if not items:
            continue
        # Un draft previo del mismo usuario/token gana (one-draft-per-user);
        # el cart legado solo se porta si no colisiona.
        if cart.user_id and Order.objects.filter(
                user_id=cart.user_id, status='DRAFT').exists():
            continue
        if cart.cart_token and Order.objects.filter(
                cart_token=cart.cart_token).exists():
            continue
        order = Order.objects.create(
            order_number=f'PY-MIG-{uuid.uuid4().hex[:10].upper()}',
            user_id=cart.user_id,
            status='DRAFT',
            cart_token=cart.cart_token,
            voucher_code=cart.voucher.code if cart.voucher_id else '',
        )
        for item in items:
            if item.product_id is None:
                continue
            OrderItem.objects.create(
                order=order,
                product_id=item.product_id,
                variant_id=item.variant_id,
                product_name=item.product.name,
                variant_label='',
                sku=item.variant.sku if item.variant_id else item.product.sku,
                unit_price=item.unit_price,
                quantity=item.quantity,
                subtotal=item.unit_price * item.quantity,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('cart', '0001_initial'),
        ('orders', '0006_order_cart_token_alter_order_status'),
    ]

    operations = [
        migrations.RunPython(_port_carts_to_drafts,
                             migrations.RunPython.noop),
        migrations.DeleteModel(name='CartItem'),
        migrations.DeleteModel(name='Cart'),
    ]
