"""Servicio del addon ``sale_stock_margin`` — bridge ``sale_stock`` + ``sale_margin``.

Adaptación de Odoo ``sale_stock_margin``, que **no aporta modelos**: sólo
sobreescribe ``sale.order.line._compute_purchase_price`` para que, cuando la
línea tiene cantidad entregada, el ``purchase_price`` (base de costo del margen)
sea el **promedio ponderado** entre la parte entregada (a su costo unitario real
de entrega) y la parte restante (al costo estándar del producto).

Como Odoo no tiene modelo aquí, este addon es **behavior-only** (sin tablas): la
lógica vive como servicio que opera sobre los dos modelos relacionados ya
existentes — ``line.delivery`` (``sale_stock``) y ``line.margin``
(``sale_margin``) — y actualiza el snapshot de margen. El costo unitario real de
entrega no se rastrea en este stack (no hay movimientos de stock valuados): se
recibe como parámetro y por defecto cae al costo estándar del producto (Clausula
5 — no se fabrica el sub-sistema de valuación de inventario).
"""
from decimal import ROUND_HALF_UP, Decimal

from addons.sale_margin.models import SaleOrderLineMargin


def recompute_purchase_price(line, delivered_unit_cost=None) -> Decimal:
    """Recalcula el ``purchase_price`` del margen ponderando por entrega.

    Réplica de Odoo ``sale_stock_margin._compute_purchase_price``:

    - Sin entrega (``qty_delivered <= 0``) → costo estándar del producto.
    - Con entrega parcial/total → ``(qd*cu + qr*cs) / (qd + qr)`` donde ``qd`` es
      la cantidad entregada a su costo unitario ``cu`` (``delivered_unit_cost``,
      por defecto el costo estándar) y ``qr`` la restante a costo estándar ``cs``.

    Crea el ``SaleOrderLineMargin`` si la línea aún no tiene uno y persiste el
    nuevo ``purchase_price``. Devuelve el valor calculado.
    """
    prod = line.product
    std_cost = prod.cost if prod and prod.cost is not None else Decimal('0.00')

    delivery = getattr(line, 'delivery', None)
    qty_delivered = delivery.qty_delivered if delivery is not None else 0
    qty_ordered = line.product_uom_qty

    if qty_delivered <= 0 or qty_ordered <= 0:
        purch = std_cost
    else:
        unit_cost = (
            Decimal(str(delivered_unit_cost))
            if delivered_unit_cost is not None else std_cost
        )
        qty_remaining = max(qty_ordered - qty_delivered, 0)
        total_qty = qty_delivered + qty_remaining
        purch = (
            (Decimal(qty_delivered) * unit_cost + Decimal(qty_remaining) * std_cost)
            / Decimal(total_qty)
        ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    margin = getattr(line, 'margin', None)
    if margin is None:
        margin = SaleOrderLineMargin(line=line)
    margin.purchase_price = purch
    margin.save()
    return purch
