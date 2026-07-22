"""V2 unificación orders→sale: porta los carritos vivos del strangler.

Las filas ``orders_order`` en estado ``DRAFT`` (los carritos que S1–S4
sirvieron desde el strangler) se portan a ``sale_order`` +
``sale_order_line`` — el canónico que el flujo vivo consume desde V2 — y
se eliminan del strangler. El ``voucher_code`` string del draft se
re-ancla como ``SaleOrderCoupon`` (H-CART-CL-02). Sin reversa: el
ejecutor aceptó el riesgo (sin datos en producción; base recreable).
"""
from django.db import migrations


def port_draft_orders(apps, schema_editor):
    Order           = apps.get_model('orders', 'Order')
    SaleOrder       = apps.get_model('sale', 'SaleOrder')
    SaleOrderLine   = apps.get_model('sale', 'SaleOrderLine')
    SaleOrderCoupon = apps.get_model('sale_loyalty', 'SaleOrderCoupon')
    Voucher         = apps.get_model('loyalty', 'Voucher')

    for order in Order.objects.filter(status='DRAFT'):
        sale_order = SaleOrder.objects.create(
            partner_id=order.user_id,
            cart_token=order.cart_token,
            state='draft',
            guest_email=order.guest_email or '',
            notes=order.notes,
        )
        for item in order.items.all():
            if item.product_id is None:
                continue  # producto hard-deleted: la línea no es portable
            SaleOrderLine.objects.create(
                order=sale_order,
                product_id=item.product_id,
                variant_id=item.variant_id,
                name=item.product_name,
                product_uom_qty=item.quantity,
                price_unit=item.unit_price,
            )
        if order.voucher_code:
            voucher = Voucher.objects.filter(code=order.voucher_code).first()
            if voucher is not None:
                SaleOrderCoupon.objects.create(order=sale_order,
                                               voucher=voucher)
        order.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('sale', '0007_saleorder_guest_email_saleorder_notes'),
        ('sale_loyalty', '0001_initial'),
        ('loyalty', '0001_initial'),
        ('orders', '0008_alter_orderaddress_order_alter_orderstatuslog_order'),
    ]

    operations = [
        migrations.RunPython(port_draft_orders, migrations.RunPython.noop),
    ]
