"""Servicio de valoración de inventario — addon ``stock_account``.

Adaptación fiel de la lógica de valoración de Odoo
(``stock_account/models/product.py``, verificado en 18):
``_prepare_in_svl_vals`` (o18:240), ``_prepare_out_svl_vals`` (o18:263) y
``_run_fifo`` (o18:367). Traza el **costo unitario real de entrega**: cada
salida crea una ``StockValuationLayer`` con el ``unit_cost`` calculado por el
método de costeo del producto.

- **Entrada (receive):** crea una SVL positiva con ``remaining_qty`` y — en
  AVCO — recalcula el promedio móvil ``standard_price = valor_total / qty_total``.
- **Salida (deliver):**

  - ``standard``/``average`` → ``unit_cost = standard_price`` del producto.
  - ``fifo`` → consume las SVL de entrada más antiguas (``remaining_qty > 0``)
    y promedia su costo (réplica de ``_run_fifo``).

  La SVL de salida es negativa en cantidad y valor.
- **value_move:** despacha entrada vs salida según el ``usage`` de las
  ubicaciones del ``StockMove`` (interna ← no-interna = entrada; interna →
  no-interna = salida; interna ↔ interna = transferencia sin valuación).
"""
from decimal import Decimal

from django.db.models import Sum

from addons.stock.models.stock_location import StockLocation
from addons.stock_account.models.product_costing import ProductCosting
from addons.stock_account.models.stock_valuation_layer import StockValuationLayer


def _q2(value) -> Decimal:
    """Redondeo a 2 decimales (moneda)."""
    return Decimal(value).quantize(Decimal('0.01'))


def receive(product, quantity, unit_cost, move=None, cost_method=None):
    """Valúa una entrada: crea la SVL positiva y recalcula AVCO.

    Réplica de ``_prepare_in_svl_vals`` + el recálculo de ``standard_price`` de
    AVCO al recibir (Odoo ``_change_standard_price``/``_update_standard_price``).
    """
    quantity = Decimal(quantity)
    unit_cost = Decimal(unit_cost)
    costing = ProductCosting.for_product(product, cost_method=cost_method)
    value = _q2(unit_cost * quantity)

    layer = StockValuationLayer.objects.create(
        product_id=product, quantity=quantity, unit_cost=unit_cost, value=value,
        remaining_qty=quantity, remaining_value=value, stock_move_id=move,
        description='Entrada valuada',
    )

    if costing.cost_method == ProductCosting.COST_AVERAGE:
        # AVCO: nuevo promedio = valor_total_a_la_mano / qty_total_a_la_mano.
        qty_on_hand = _product_qty_svl(product)
        value_on_hand = _product_value_svl(product)
        if qty_on_hand > 0:
            costing.standard_price = (value_on_hand / qty_on_hand).quantize(Decimal('0.0001'))
            costing.save(update_fields=['standard_price', 'updated_at'])
    elif costing.cost_method == ProductCosting.COST_STANDARD and costing.standard_price == 0:
        # Estándar sin costo fijado aún: adopta el costo de la primera entrada.
        costing.standard_price = unit_cost.quantize(Decimal('0.0001'))
        costing.save(update_fields=['standard_price', 'updated_at'])
    return layer


def deliver(product, quantity, move=None, cost_method=None):
    """Valúa una salida: crea la SVL negativa con el costo del método.

    Réplica de ``_prepare_out_svl_vals`` + ``_run_fifo``. Devuelve la SVL de
    salida — su ``unit_cost`` es el **costo unitario real de esa entrega**.
    """
    quantity = Decimal(quantity)
    costing = ProductCosting.for_product(product, cost_method=cost_method)

    if costing.cost_method == ProductCosting.COST_FIFO:
        unit_cost, total_value = _run_fifo(product, quantity)
    else:
        unit_cost = costing.standard_price
        total_value = _q2(unit_cost * quantity)

    layer = StockValuationLayer.objects.create(
        product_id=product, quantity=-quantity, unit_cost=unit_cost,
        value=-total_value, remaining_qty=Decimal('0.00'),
        remaining_value=Decimal('0.00'), stock_move_id=move,
        description='Salida valuada',
    )
    return layer


def _run_fifo(product, quantity):
    """Consume las SVL de entrada más antiguas para valuar ``quantity`` (Odoo _run_fifo).

    Devuelve ``(unit_cost_promedio, valor_total)``. Escribe el saldo consumido
    en ``remaining_qty``/``remaining_value`` de cada candidata.
    """
    qty_to_take = Decimal(quantity)
    tmp_value = Decimal('0.00')
    candidates = StockValuationLayer.objects.filter(
        product_id=product, remaining_qty__gt=0,
    ).order_by('id')
    last_unit_cost = Decimal('0.0000')
    for candidate in candidates:
        if qty_to_take <= 0:
            break
        candidate_unit_cost = (candidate.remaining_value / candidate.remaining_qty)
        last_unit_cost = candidate_unit_cost
        qty_taken = min(qty_to_take, candidate.remaining_qty)
        value_taken = _q2(qty_taken * candidate_unit_cost)
        candidate.remaining_qty = candidate.remaining_qty - qty_taken
        candidate.remaining_value = candidate.remaining_value - value_taken
        candidate.save(update_fields=['remaining_qty', 'remaining_value', 'updated_at'])
        qty_to_take -= qty_taken
        tmp_value += value_taken

    if qty_to_take > 0:
        # Stock negativo: valúa el faltante al último costo FIFO conocido
        # (Odoo hace un ajuste posterior con _fifo_vacuum; aquí valúa directo).
        fallback = last_unit_cost or ProductCosting.for_product(product).standard_price
        tmp_value += _q2(qty_to_take * fallback)

    total_value = _q2(tmp_value)
    unit_cost = (total_value / quantity).quantize(Decimal('0.0001')) if quantity else Decimal('0.0000')
    return unit_cost, total_value


def value_move(move, unit_cost=None, cost_method=None):
    """Valúa un ``StockMove`` hecho según el ``usage`` de sus ubicaciones.

    - No-interna → interna = **entrada** (receipt): usa ``unit_cost`` (o el
      ``standard_price`` del producto si no se da).
    - Interna → no-interna = **salida** (delivery): usa el método de costeo.
    - Interna ↔ interna = transferencia sin cambio de valor (devuelve ``None``).
    """
    src_internal = move.location.usage == StockLocation.USAGE_INTERNAL
    dest_internal = move.location_dest.usage == StockLocation.USAGE_INTERNAL
    qty = move.quantity or move.product_uom_qty

    if not src_internal and dest_internal:
        if unit_cost is None:
            unit_cost = ProductCosting.for_product(move.product).standard_price
        return receive(move.product, qty, unit_cost, move=move, cost_method=cost_method)
    if src_internal and not dest_internal:
        return deliver(move.product, qty, move=move, cost_method=cost_method)
    return None


def _product_qty_svl(product) -> Decimal:
    """Cantidad total valuada a la mano (Odoo quantity_svl)."""
    total = StockValuationLayer.objects.filter(product_id=product).aggregate(
        s=Sum('quantity'),
    )['s']
    return total or Decimal('0.00')


def _product_value_svl(product) -> Decimal:
    """Valor total valuado a la mano (Odoo value_svl)."""
    total = StockValuationLayer.objects.filter(product_id=product).aggregate(
        s=Sum('value'),
    )['s']
    return total or Decimal('0.00')
