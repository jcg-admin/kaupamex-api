"""Desglose de importes para las superficies de salida del comprador.

**Qué resuelve.** El recibo PDF y el payload del pedido presentan los mismos
cinco importes (``subtotal``/``tax``/``shipping_cost``/``discount``/``total``).
Hasta E4 los leían de ``OrderValue`` — columnas de cabecera del espejo. Aquí se
componen del **canónico**, preservando exactamente las mismas claves para no
romper el contrato que consume el UI.

**Dónde vive y por qué.** La composición importa de tres addons
(``sale`` + ``delivery`` + ``sale_loyalty``), así que no puede vivir en ninguno
de ellos sin invertir su dependencia: ``sale`` no sabe qué es una línea de
envío. En la referencia, el desglose que ve el comprador se compone en la
**capa de presentación** (la plantilla de ``website_sale`` combina
``amount_untaxed``, ``amount_delivery`` y ``amount_total``), no en un modelo.
``orders`` es esa capa aquí: consumidor de los tres, sin nadie que dependa de
él. Cuando el espejo se retire (E5) esta función acompaña a la superficie de
factura, no desaparece.

**Divergencia deliberada con el espejo — la base gravable del IVA.**
``confirm_draft_order`` calculaba ``tax`` sobre ``net = subtotal - discount``
(``sale/services.py:377``), es decir **excluyendo el envío**. El canónico extrae
el IVA por línea, así que la línea de envío **también** tributa. El **total no
cambia** — sólo se reparte distinto entre base e impuesto. La forma canónica es
la correcta: el flete es un concepto con su propio IVA, que es justamente lo que
H-API-35 exige para que el CFDI cuadre. Ver H-API-41.
"""
from decimal import Decimal

from addons.delivery.models.sale_order import amount_delivery
from addons.sale_loyalty.models.sale_order import amount_reward


def order_amounts(sale_order) -> dict:
    """Devuelve el desglose del comprador con las claves del contrato legacy.

    ``subtotal`` es el importe **de producto** (bruto, antes del descuento). Se
    obtiene por composición —total menos envío más descuento— en vez de con un
    agregado "sólo producto": así cada término lo aporta su dueño y no hace
    falta que ningún addon conozca los marcadores del otro.

    Devuelve ceros si ``sale_order`` es ``None`` (órdenes espejo huérfanas del
    histórico), para que la superficie renderice sin datos en vez de romper.
    """
    if sale_order is None:
        zero = Decimal('0.00')
        return {'subtotal': zero, 'tax': zero, 'shipping_cost': zero,
                'discount': zero, 'total': zero}

    shipping = amount_delivery(sale_order)
    discount = amount_reward(sale_order)
    total    = sale_order.amount_total
    return {
        'subtotal':      total - shipping + discount,
        'tax':           sale_order.amount_tax,
        'shipping_cost': shipping,
        'discount':      discount,
        'total':         total,
    }
