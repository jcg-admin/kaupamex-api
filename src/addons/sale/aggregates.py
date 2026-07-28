"""Motor SQL de importes sobre ``sale.order`` — addon ``sale``.

**Por qué existe este módulo.** Los importes del canónico son métodos Python
que iteran líneas (``SaleOrder.amount_total()`` →
``SaleOrderLine.price_total()``), y SQL no puede ``Sum()`` un método. Mientras
envío y descuento vivían como escalares del espejo, el único agregado posible
era sobre ``orders.OrderValue`` — de ahí que todo reporte de dinero siguiera
atado al espejo (H-API-30, defecto de agregación).

E1-bis cambió la premisa: **todos** los montos son ahora datos de línea con
columnas reales (``price_unit``, ``product_uom_qty``, ``discount``), incluidos
los que no son de producto. Eso hace el agregado **expresable en SQL**.

**Alcance de este módulo — sólo el motor genérico.** Fiel al reparto de la
referencia: ``sale._compute_amounts`` (``sale/models/sale_order.py:513``) suma
**todas** las líneas y no sabe qué es una línea de envío; el desglose que
filtra ``is_delivery`` vive en el módulo que conoce el envío
(``website_sale._compute_amount_delivery``, :62-69), no en ``sale``. Aquí
queda entonces la expresión de total y el constructor parametrizable
``line_sum_subquery``; cada addon contribuyente arma **su** desglose con él:

- ``delivery/aggregates.py``    → importe de envío.
- ``sale_loyalty/aggregates.py`` → importe de recompensa.

**Paridad exacta con el método Python, no aproximada.**
``price_total()`` cuantiza **por línea** antes de sumar
(``sale_order_line.py:84-87``); esta expresión hace ``ROUND(..., 2)`` por línea
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


# Equivalente SQL de ``SaleOrder.amount_total()`` — y por tanto de
# ``OrderValue.total`` del espejo para toda venta nacida después de E1-bis.
AMOUNT_TOTAL_SQL = line_sum_subquery()


def with_amounts(queryset):
    """Anota un queryset de ``SaleOrder`` con su total agregable.

    Uso::

        with_amounts(SaleOrder.objects.filter(...)).aggregate(
            revenue=Sum('amount_total_sql'), order_count=Count('id'))

    El ``Count('id')`` es correcto porque la anotación es un ``Subquery``: una
    fila por orden, sin fan-out de líneas.
    """
    return queryset.annotate(amount_total_sql=AMOUNT_TOTAL_SQL)
