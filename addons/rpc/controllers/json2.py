"""``POST /json/2/<model>/<method>`` — el despacho genérico a los modelos.

Porte de ``odoo19c: addons/rpc/controllers/json2.py`` (``odoo-tools@abe4040e``,
LGPL-3 → copia con adaptación y atribución, DEC-KX-03).

Es el endpoint programático del producto: el cliente nombra un modelo y un
método, y el servidor los resuelve **en tiempo de petición**. Esa es justamente
la razón de que el gate de ``get_public_method`` exista — en una vista declarada
el método lo fija el código; aquí lo elige quien llama.

Los dos gates, y el orden importa
-----------------------------------

1. **``HasCapability('rpc.call')``** (DEC-11) decide si *este usuario* puede
   usar el despacho programático. Es nuestro, no de la referencia: allá el
   endpoint es ``auth='bearer'`` y el control de acceso vive dentro del ORM.
2. **``get_public_method``** decide si *ese símbolo* es invocable en absoluto.
   Es de la referencia, y no lo sustituye la capacidad: una capacidad concedida
   no debe convertir un método privado en API (ver :ref:`h-api-638`).

La traducción de errores, MEDIDA contra DRF 3.16.1
----------------------------------------------------

La referencia levanta excepciones de werkzeug. Aquí el mapeo se derivó leyendo
``rest_framework/views.py:exception_handler`` en el paquete instalado, no de
memoria:

.. list-table::
   :header-rows: 1

   * - Situación
     - Excepción
     - Cómo llega a su código
   * - modelo inexistente
     - ``NotFound``
     - ``APIException`` → 404 directo
   * - método inexistente
     - ``AttributeError`` → ``NotFound``
     - **se traduce**: DRF no la conoce y devolvería ``None`` → 500
   * - método no invocable
     - ``AccessError``
     - **no se traduce**: es ``PermissionDenied`` de Django, y el handler de
       DRF ya la mapea a 403 (``views.py``)
   * - ``@api.model`` con ``ids`` · firma que no liga
     - ``UnprocessableEntity``
     - clase **declarada aquí**: DRF 3.16.1 tiene el 422 en ``status.py`` pero
       ninguna ``APIException`` que lo lleve

Lo que este árbol hace distinto, y por qué
--------------------------------------------

La referencia despacha ``func(records, **kwargs)``, donde ``records`` es un
recordset. Aquí ``self`` es **un registro**, no un conjunto: medido sobre los
addons portados, 102 archivos escriben ``self.campo`` y sólo 2 iteran ``self``.
Así que el análogo del recordset es el ``QuerySet``, y el análogo de
``Model.browse(ids)`` es ``filter(pk__in=ids)`` — con la misma propiedad que la
referencia le pide: no toca la base hasta que alguien lo recorre.
"""
import inspect

from django.db import models
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import APIException, NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from addons.authz.permissions import require_capability
from orm.registry import model_by_odoo_name
from service.model import get_public_method


class UnprocessableEntity(APIException):
    """422 — la petición se entiende pero sus argumentos no encajan.

    ≙ ``werkzeug.exceptions.UnprocessableEntity``, que la referencia importa.
    **DRF 3.16.1 no trae una clase para este código**: su escalera de
    ``APIException`` salta de 415 a 429, aunque ``status.py:73`` sí declara
    ``HTTP_422_UNPROCESSABLE_ENTITY``. Medido en el paquete instalado.
    """

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = 'Los argumentos de la llamada no encajan con el método.'
    default_code = 'unprocessable_entity'


def resolve_call(model_name, method_name, ids, kwargs=None):
    """Resuelve la llamada, o levanta la excepción HTTP que corresponda.

    Separado de la vista a propósito: todo el contrato —los cuatro rechazos y
    sus códigos— vive aquí, y así se prueba sin montar una petición.

    :returns: ``(model, func, records)``. ``func`` viene **sin ligar**, igual
        que en la referencia, salvo cuando es un ``classmethod`` de nivel de
        modelo (que ya viene ligado a la clase y no recibe registros).
    """
    kwargs = kwargs or {}

    model = model_by_odoo_name(model_name)
    if model is None:
        # ≙ `raise NotFound(f"the model {__model__!r} does not exist")`.
        raise NotFound(f"the model '{model_name}' does not exist")

    try:
        func = get_public_method(model(), method_name)
    except AttributeError as exc:
        # La ÚNICA traducción real: sin ella DRF no reconoce AttributeError,
        # su handler devuelve None y el cliente recibe un 500 por un método mal
        # escrito. `AccessError` NO se captura — ya es 403 por sí sola.
        raise NotFound(exc.args[0]) from exc

    model_level = getattr(func, '_api_model', False)
    if model_level and ids:
        raise UnprocessableEntity(
            f'cannot call {model_name}.{method_name} with ids'
        )

    # ≙ `Model.browse(ids)`: perezoso, no consulta hasta que se recorre.
    records = model.objects.filter(pk__in=list(ids))

    # La firma la valida `inspect`, no un chequeo a mano: así el mensaje de
    # error es el de Python y cubre argumentos de más, de menos y mal nombrados.
    signature = inspect.signature(func)
    try:
        if model_level:
            signature.bind(**kwargs)
        else:
            signature.bind(records, **kwargs)
    except TypeError as exc:
        raise UnprocessableEntity(exc.args[0]) from exc

    return model, func, records


@extend_schema(
    tags=['rpc'],
    summary='Invocar un método de modelo por su nombre',
    description=(
        'Despacho genérico: el cuerpo lleva `ids` (los registros sobre los que '
        'opera), `context` y el resto de argumentos con nombre del método. '
        'Requiere la capacidad `rpc.call`; además, el método debe ser '
        'invocable remotamente (público, no `@api.private`).'
    ),
    responses={
        200: OpenApiResponse(description='El valor de retorno del método, en JSON.'),
        403: OpenApiResponse(description='Sin capacidad, o método no invocable.'),
        404: OpenApiResponse(description='El modelo o el método no existen.'),
        422: OpenApiResponse(description='Los argumentos no encajan con la firma.'),
    },
)
@api_view(['POST'])
@require_capability('rpc.call')
def json2_rpc(request, model_name, method_name):
    """La vista: parsea el cuerpo, delega en ``resolve_call`` y ejecuta."""
    payload = dict(request.data or {})
    ids = payload.pop('ids', ())
    # `context` se acepta y se ignora por ahora: la referencia lo usa para
    # `with_context`, mecanismo que este árbol no tiene. Aceptarlo y no
    # honrarlo en silencio sería peor, así que se rechaza si trae contenido.
    context = payload.pop('context', None)
    if context:
        raise UnprocessableEntity(
            'context todavía no se honra: este árbol no tiene with_context'
        )

    _model, func, records = resolve_call(model_name, method_name, ids, payload)

    # Si el método levanta `AccessError`, se deja pasar sin envolver: es
    # `PermissionDenied` de Django y el handler de DRF la mapea a 403. Un
    # `try/except ... raise` aquí no haría nada salvo esconder su origen.
    result = func(**payload) if getattr(func, '_api_model', False) \
        else func(records, **payload)

    if isinstance(result, models.QuerySet):
        result = list(result.values_list('pk', flat=True))
    elif isinstance(result, models.Model):
        # ≙ `if isinstance(result, BaseModel): result = result.ids`.
        result = [result.pk]

    return Response(result)


@extend_schema(exclude=True)
@api_view(['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@permission_classes([AllowAny])
def json2_404(request, subpath=''):
    """Catch-all de ``/json/2`` — ≙ ``web_json_2_404`` de la referencia.

    Devuelve el mismo 404 con pista que la fuente: un cliente que se equivoca
    de forma recibe la forma correcta, no un 404 mudo del router.

    Es ``AllowAny`` a propósito, como su fuente (``auth='public'``): decirle a
    un desconocido *cuál es la forma de la URL* no revela nada — la forma está
    documentada. Lo que sí exige capacidad es el despacho, que es el que actúa.
    """
    raise NotFound('Did you mean POST /json/2/<model>/<method>?')
