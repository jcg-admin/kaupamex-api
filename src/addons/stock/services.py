"""``InventoryService`` — disponibilidad y movimiento de existencias.

Adaptación fiel de la aritmética de ``odoo19c: addons/stock/models/stock_quant.py``
(``odoo-tools@622ddc2a``):

- ``:87-90,119-122`` — ``available_quantity`` es un **computado**
  ``quantity - reserved_quantity``. La existencia no es una columna del
  producto: se **deriva** de los quants.
- ``:635`` — la agregación por producto es ``SUM(quantity - reserved_quantity)``
  sobre todos sus quants.

**Procedencia y por qué está aquí.** El servicio vivía en
``inventory/services.py``. La familia ``inventory`` se disolvió en ``stock``
(:ref:`analisis-panorama-familias-strangler`), los modelos viajaron
(``stock_quant``, ``stock_move``, ``stock_lot``…) pero el servicio **no**: quedó
un ``from addons.inventory.services import InventoryService`` colgado en
``sale/services.py:31``. Ver H-API-212.

**Un solo eje de producto.** La firma anterior aceptaba ``{'product':…,
'variant':…}`` — el modelo plano previo a la separación. En la referencia el
stock se lleva por **variante** (``product.product``), y la línea de venta
apunta a la variante (``odoo19c: addons/sale/models/sale_order_line.py:83-88``);
la plantilla (``product.template``) no tiene existencias propias. Por eso el
servicio se indexa por ``ProductProduct`` y el eje ``variant`` desaparece: era
el mismo dato dos veces. Ver :ref:`analisis-destino-por-addon-del-fk-producto` §2.
"""
from collections import OrderedDict
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Sum

from addons.stock.models import StockLocation, StockQuant

ZERO = Decimal('0.00')


class InsufficientStockError(Exception):
    """No hay existencias suficientes para cubrir el movimiento solicitado."""

    def __init__(self, message, items=None):
        super().__init__(message)
        self.items = items or []


def _aggregate(items):
    """Suma las cantidades pedidas por variante, preservando el orden.

    Dos líneas del mismo SKU compiten por el mismo stock; evaluarlas por
    separado aprobaría el doble de lo disponible.
    """
    wanted = OrderedDict()
    for item in items:
        product = item.get('product')
        if product is None:
            continue
        qty = Decimal(item.get('quantity') or 0)
        obj, total = wanted.get(product.pk, (product, ZERO))
        wanted[product.pk] = (obj, total + qty)
    return list(wanted.values())


class InventoryService:
    """Fachada de existencias sobre ``stock.quant``."""

    @staticmethod
    def available_quantity(product) -> Decimal:
        """``SUM(quantity - reserved_quantity)`` del producto (odoo19c :635)."""
        total = (StockQuant.objects
                 .filter(product=product)
                 .aggregate(total=Sum(F('quantity') - F('reserved_quantity')))
                 ['total'])
        return Decimal(total) if total is not None else ZERO

    @classmethod
    def check_availability(cls, items):
        """Devuelve la lista de faltantes; vacía si todo alcanza.

        Cada faltante es ``{'product':…, 'requested':…, 'available':…}``.
        NO reserva: es una lectura. La reserva efectiva la hace ``decrement``
        bajo ``SELECT FOR UPDATE``.
        """
        insufficient = []
        for product, requested in _aggregate(items):
            available = cls.available_quantity(product)
            if requested > available:
                insufficient.append({
                    'product': product,
                    'requested': requested,
                    'available': available,
                })
        return insufficient

    @classmethod
    @transaction.atomic
    def decrement(cls, items):
        """Descuenta las cantidades de los quants del producto.

        Bloquea las filas con ``select_for_update`` para que dos checkouts
        concurrentes no lean el mismo saldo. Consume ubicación por ubicación en
        orden de id; si el total no alcanza, levanta ``InsufficientStockError``
        y la transacción entera revierte.
        """
        for product, requested in _aggregate(items):
            remaining = requested
            quants = (StockQuant.objects
                      .select_for_update()
                      .filter(product=product)
                      .order_by('pk'))
            for quant in quants:
                if remaining <= ZERO:
                    break
                free = quant.quantity - quant.reserved_quantity
                if free <= ZERO:
                    continue
                take = min(free, remaining)
                quant.quantity -= take
                quant.save(update_fields=['quantity', 'updated_at'])
                remaining -= take
            if remaining > ZERO:
                raise InsufficientStockError(
                    'Existencias insuficientes para %s.' % product,
                    items=[{'product': product, 'requested': requested,
                            'available': requested - remaining}],
                )

    @classmethod
    @transaction.atomic
    def restore(cls, items, reference: str = '', created_by=None):
        """Devuelve cantidades al almacén (cancelación / devolución).

        Suma al primer quant del producto; si no tiene ninguno, lo crea en la
        ubicación interna por defecto. ``reference`` y ``created_by`` son
        trazabilidad del llamador — no alteran la aritmética; el asiento
        narrativo lo lleva ``BusinessEvent``, no el quant.
        """
        for product, qty in _aggregate(items):
            if qty <= ZERO:
                continue
            quant = (StockQuant.objects
                     .select_for_update()
                     .filter(product=product)
                     .order_by('pk')
                     .first())
            if quant is None:
                quant = StockQuant(
                    product=product, location=_default_internal_location(),
                    quantity=ZERO, reserved_quantity=ZERO,
                )
            quant.quantity += qty
            quant.save()


def _default_internal_location():
    """Ubicación interna por defecto, creada al vuelo si el árbol está vacío.

    La referencia siembra ``stock.stock_location_stock`` en ``data/``; este
    árbol aún no porta esos datos, así que el servicio garantiza el destino en
    vez de fallar al restaurar.
    """
    location, _ = StockLocation.objects.get_or_create(
        name='WH/Stock', usage='internal',
    )
    return location
