"""
UC-INC-01 — Verificar Propiedad de Orden (H-ADM-006).

Patrón centralizado: filter(order_number, user).first() → 404.
RNF-SEC-003: nunca HTTP 403, siempre 404 si no existe o es ajena.
Incluido por UC-ORD-02/04/05/06, UC-PAY-05/06/07, UC-LOG-03/07.
"""
from rest_framework.response import Response
from .models import Order


def get_own_order(order_number: str, user, select_related=None, prefetch_related=None):
    """
    Retorna la Order del usuario o None.
    Implementa UC-INC-01 (RNF-SEC-003): mismo comportamiento si no existe
    o si pertenece a otro usuario — el caller retorna 404.

    :param order_number: Order.order_number
    :param user: User autenticado
    :param select_related: lista de fields para select_related
    :param prefetch_related: lista de fields para prefetch_related
    :returns: Order o None
    """
    qs = Order.objects.filter(order_number=order_number, user=user)
    if select_related:
        qs = qs.select_related(*select_related)
    if prefetch_related:
        qs = qs.prefetch_related(*prefetch_related)
    return qs.first()


NOT_FOUND_RESPONSE = {
    'detail':       'Orden no encontrada.',
    'codigo_error': 'ORDER_NOT_FOUND',
}
