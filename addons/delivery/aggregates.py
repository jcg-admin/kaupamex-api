"""Desglose SQL del importe de envío — addon ``delivery``.

Contraparte agregable de ``delivery/models/sale_order.py``: si la línea de
envío la contribuye este addon, el **importe agregado** de esa línea también.

Fiel al reparto de la referencia: ``sale`` provee el motor genérico
(``sale/aggregates.py::line_sum_subquery``) y no sabe qué es una línea de
envío; quien filtra ``is_delivery`` es el módulo que conoce el envío — en Odoo
``website_sale._compute_amount_delivery`` (``website_sale/models/sale_order.py:62-69``),
que también resuelve el agregado filtrando ``order_line.filtered('is_delivery')``.
La dirección de dependencia se mantiene: ``delivery`` importa de ``sale``,
nunca al revés.
"""
from django.db.models import Q

from addons.sale.aggregates import line_sum_subquery

AMOUNT_DELIVERY_SQL = line_sum_subquery(Q(is_delivery=True))


def with_delivery_amount(queryset):
    """Anota un queryset de ``SaleOrder`` con su importe de envío."""
    return queryset.annotate(amount_delivery_sql=AMOUNT_DELIVERY_SQL)
