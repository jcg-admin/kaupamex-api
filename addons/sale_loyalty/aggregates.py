"""Desglose SQL del importe de recompensa — addon ``sale_loyalty``.

Contraparte agregable de ``sale_loyalty/models/sale_order.py``: si la línea de
recompensa la contribuye este addon, el **importe agregado** de esa línea
también. Simétrico de ``delivery/aggregates.py`` y por la misma razón —
``sale`` provee el motor genérico y no sabe qué es una recompensa.

El importe es **negativo** (la línea lleva ``price_unit`` negativo), así que
suma directo al total sin invertir el signo en el llamador.
"""
from django.db.models import Q

from addons.sale.aggregates import line_sum_subquery

AMOUNT_REWARD_SQL = line_sum_subquery(Q(is_reward=True))


def with_reward_amount(queryset):
    """Anota un queryset de ``SaleOrder`` con su importe de descuento."""
    return queryset.annotate(amount_reward_sql=AMOUNT_REWARD_SQL)
