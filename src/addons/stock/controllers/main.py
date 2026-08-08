"""``main`` — el panel de inventario del operador.

Adaptación de ``stock/controllers/main.py``. La referencia expone el
inventario por la vista de back-office de Odoo, no por HTTP; su ``main.py``
sirve otra cosa. Por eso esta superficie es **forma propia declarada**: el
back-office de este producto es un SPA, así que el panel necesita un
endpoint.

Lo que **no** es propio es el dato: se agrega sobre ``StockQuant``, el modelo
que la referencia usa para el mismo cálculo (cantidad a mano por producto y
ubicación, menos lo reservado).

Estilo: dos lecturas de un verbo → vistas función. Gateadas por la capacidad
``logistics``, que ``delivery`` ya declara para el dominio (no se inventa una
nueva; ver H-API-283).
"""
from django.db.models import F, Sum
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.authz.permissions import require_capability
from addons.stock.models import StockQuant

#: Umbral por defecto de "poco stock". Configurable por query param — no se
#: fija a fuego porque cada catálogo tiene su propia rotación.
DEFAULT_LOW_STOCK_THRESHOLD = 5


def _available():
    """Disponible = a mano − reservado, que es como lo calcula la referencia.

    Un quant con 10 unidades y 10 reservadas no es stock disponible: está
    comprometido con una orden.
    """
    return StockQuant.objects.annotate(
        available=F('quantity') - F('reserved_quantity'))


@extend_schema(
    tags=['inventory'],
    summary='Panel de inventario',
    responses={200: None},
)
@api_view(['GET'])
@require_capability('logistics')
def inventory_dashboard(request):
    """Los agregados del panel: totales y conteos por estado."""
    quants = _available()
    totals = quants.aggregate(
        on_hand=Sum('quantity'), reserved=Sum('reserved_quantity'))
    return Response({
        'products_tracked': quants.values('product').distinct().count(),
        'locations': quants.values('location').distinct().count(),
        'quantity_on_hand': totals['on_hand'] or 0,
        'quantity_reserved': totals['reserved'] or 0,
        'out_of_stock': quants.filter(available__lte=0).count(),
    })


@extend_schema(
    tags=['inventory'],
    summary='Alertas de stock bajo',
    parameters=[
        OpenApiParameter('threshold', OpenApiTypes.NUMBER,
                         description='Por debajo de este disponible, alerta.'),
    ],
    responses={200: None},
)
@api_view(['GET'])
@require_capability('logistics')
def inventory_alerts(request):
    """Los productos por debajo del umbral, del más crítico al menos."""
    raw = request.query_params.get('threshold')
    try:
        threshold = float(raw) if raw else DEFAULT_LOW_STOCK_THRESHOLD
    except (TypeError, ValueError):
        threshold = DEFAULT_LOW_STOCK_THRESHOLD

    rows = (
        _available()
        .filter(available__lte=threshold)
        .select_related('product', 'location')
        .order_by('available')[:200]
    )
    return Response({
        'threshold': threshold,
        'count': len(rows),
        'results': [
            {
                'product_id': row.product_id,
                'product': str(row.product),
                'location': str(row.location),
                'quantity': row.quantity,
                'reserved': row.reserved_quantity,
                'available': row.available,
            }
            for row in rows
        ],
    })
