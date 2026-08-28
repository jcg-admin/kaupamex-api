"""Endpoint de lectura del bus — la traducción de ``_poll`` a HTTP.

DEC-AF-06 adopta de la referencia la cola y el punto de extensión, y sustituye
el transporte: donde ella empuja por WebSocket, aquí el cliente consulta. La
propia referencia expone ``_poll`` (``bus/models/bus.py:170``), así que esto es
una de sus dos vías, no un mecanismo ajeno.

**El canal se deriva del usuario autenticado, nunca del query string.** Es la
propiedad de seguridad que la referencia señala al advertir contra el uso
directo de ``_sendone`` con un ``target`` adivinable: aquí el cliente no puede
pedir el canal de otro.
"""
from addons.authz.permissions import require_capability
from addons.bus.models import BusMessage
from addons.bus.services import channels_for_user
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from drf_spectacular.types import OpenApiTypes
from rest_framework.decorators import api_view
from rest_framework.response import Response


@extend_schema(
    tags=['bus'],
    summary='Leer las notificaciones pendientes del usuario',
    description=(
        'Devuelve los mensajes encolados para los canales del usuario '
        'autenticado. Con `last=0` entrega sólo la ventana reciente; con '
        '`last=<id>`, todo lo posterior a ese identificador. Los canales se '
        'derivan de la sesión, no del query string.'
    ),
    parameters=[
        OpenApiParameter(
            'last', OpenApiTypes.INT,
            description='Último id ya recibido por el cliente. 0 = primer sondeo.',
        ),
    ],
    responses={
        200: OpenApiResponse(description='{"last": <id>, "notifications": [...]}'),
        400: OpenApiResponse(description='INVALID_LAST'),
    },
)
@api_view(['GET'])
@require_capability('account.bus')
def bus_poll(request):
    crudo = request.query_params.get('last', '0')
    try:
        last = int(crudo)
    except (TypeError, ValueError):
        return Response(
            {'codigo_error': 'INVALID_LAST',
             'detail': 'El parámetro last debe ser un entero.'},
            status=400,
        )
    if last < 0:
        return Response(
            {'codigo_error': 'INVALID_LAST',
             'detail': 'El parámetro last no puede ser negativo.'},
            status=400,
        )

    notifications = BusMessage.poll(channels_for_user(request.user), last=last)
    # El cliente avanza su cursor con el último id devuelto; si no hubo nada,
    # conserva el que traía y no vuelve a leer la ventana desde cero.
    ultimo = notifications[-1]['id'] if notifications else last
    return Response({'last': ultimo, 'notifications': notifications})
