"""Motor SQL de importes por línea sobre ``sale.order`` — addon ``sale``.

**Por qué existe este módulo.** Los importes que no son de producto (envío,
descuento de cupón) son datos de línea con columnas reales (``price_unit``,
``product_uom_qty``, ``discount``), marcados con ``is_delivery``/``is_reward``
(E1-bis). El **total de la orden** (``amount_total``) ya no necesita este
motor —está materializado como columna, ver ``SaleOrder._compute_amounts``
(H-API-30)—; un ``Sum('amount_total')`` directo sobre ``SaleOrder`` agrega sin
``Subquery`` y sin fan-out, porque no hay join a línea que lo arriesgue.

Lo que **sí** sigue necesitando ``Subquery`` es el **desglose por marcador**:
cuánto de ``amount_total`` es envío, cuánto es descuento. Eso no es una
columna propia —``sale`` no sabe qué es una línea de envío, sólo sus
addons contribuyentes lo saben (``delivery``/``sale_loyalty``)— así que aquí
queda el motor genérico parametrizable:

- ``delivery/aggregates.py``     → importe de envío (``Q(is_delivery=True)``).
- ``sale_loyalty/aggregates.py`` → importe de recompensa (``Q(is_reward=True)``).

**Paridad exacta con el método Python, no aproximada.**
``price_total()`` cuantiza **por línea** antes de sumar
(``sale_order_line.py:85-88``); esta expresión hace ``ROUND(..., 2)`` por línea
por la misma razón. Sumar exacto y redondear al final daría diferencias de
centavos contra el total que el comprador vio — inaceptable en un reporte de
ingresos. La paridad está fijada por test
(``tests/integration/sale/test_amount_sql_paridad_e4.py``).

**Subquery, no join.** Anotar con ``Sum`` sobre ``order_line`` multiplica las
filas de la orden por sus líneas, así que un ``Count('id')`` en el mismo
``aggregate()`` contaría líneas en vez de órdenes — el defecto clásico de
fan-out. La anotación usa ``Subquery`` para que cada orden aporte una fila.
"""
from decimal import Decimal

from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce, Round

from .models import SaleOrderLine

# Dinero: 12 dígitos / 2 decimales, alineado con los campos ``Monetary`` de
# línea. Fijar el ``output_field`` es obligatorio en expresiones mixtas —
# Django no lo infiere cuando hay ``Value`` de por medio.
MONEY = DecimalField(max_digits=12, decimal_places=2)

# Total de una línea: price_unit * qty * (1 - discount/100), redondeado a
# centavos. Espejo SQL de ``SaleOrderLine.price_total()``.
LINE_TOTAL = Round(
    F('price_unit') * F('product_uom_qty')
    * (Value(Decimal('1')) - F('discount') / Value(Decimal('100'))),
    2,
    output_field=MONEY,
)


def line_sum_subquery(line_filter=None):
    """Subquery que suma ``LINE_TOTAL`` de las líneas de la orden externa.

    ``line_filter`` (un ``Q``) acota qué líneas entran. Es el punto de
    extensión para los addons contribuyentes: ``delivery`` pasa
    ``Q(is_delivery=True)``, ``sale_loyalty`` pasa ``Q(is_reward=True)``, sin
    que ``sale`` tenga que conocer ninguno de los dos.

    Devuelve ``0.00`` —no ``NULL``— cuando no hay líneas que sumar, para que un
    payload de reporte no confunda "cero" con "sin dato".
    """
    lines = SaleOrderLine.objects.filter(order=OuterRef('pk'))
    if line_filter is not None:
        lines = lines.filter(line_filter)
    lines = lines.values('order').annotate(t=Sum(LINE_TOTAL)).values('t')
    return Coalesce(Subquery(lines, output_field=MONEY),
                    Value(Decimal('0.00'), output_field=MONEY))
