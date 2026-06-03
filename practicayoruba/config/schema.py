"""Componentes de schema OpenAPI reutilizables (drf-spectacular / ADR-015).

Define el contrato de las respuestas de error de la API. El canon del
proyecto es ``codigo_error`` (no ``error_code``) — ver
``.claude/rules/`` del superproyecto y el gate canon-idioma. Estos
serializers existen SOLO para documentar la forma de los errores en el
schema; no se usan para serializar respuestas en runtime (las vistas ya
devuelven ``Response({'detail': ..., 'codigo_error': ...})`` a mano).
"""
from drf_spectacular.utils import OpenApiExample, OpenApiResponse
from rest_framework import serializers


class ErrorResponseSerializer(serializers.Serializer):
    """Forma canonica de una respuesta de error de la API PracticaYoruba.

    Todas las vistas que devuelven un error de cliente/servidor responden
    con este shape: un ``detail`` legible y un ``codigo_error`` estable
    que el frontend puede mapear a mensajes localizados.
    """

    detail = serializers.CharField(
        help_text='Mensaje legible que describe el error.',
    )
    codigo_error = serializers.CharField(
        help_text=(
            'Codigo de error estable de la API (canon del proyecto). '
            'El cliente lo usa para logica/mensajes; no cambia entre '
            'versiones del texto de detail.'
        ),
    )


def error_response(description):
    """Construye un ``OpenApiResponse`` tipado con ``ErrorResponseSerializer``.

    Atajo para declarar respuestas de error en ``@extend_schema(responses=)``
    sin repetir el ejemplo en cada vista::

        @extend_schema(responses={404: error_response('Recurso no encontrado')})
    """
    return OpenApiResponse(
        response=ErrorResponseSerializer,
        description=description,
        examples=[
            OpenApiExample(
                'Error',
                value={'detail': description, 'codigo_error': 'CODIGO_ERROR'},
                response_only=True,
            ),
        ],
    )
