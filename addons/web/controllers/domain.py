"""Validación de dominios — adaptación de ``odoo19c:
addons/web/controllers/domain.py``, licencia LGPL-3 (``web/__manifest__.py``,
``odoo-tools@622ddc2a``) — copia + adaptación con atribución (DEC-KX-03).

Cierra la tarea **#397** (auditoría ``check_mirrored_roots.py``, hueco de
porte de ``controllers/domain.py``, 13 archivos / 22 ``def`` del addon raíz
``web``).

Medición símbolo-por-símbolo (``re.findall(r'^\\s{4}def (\\w+)', ref)``, mismo
criterio que ``porte-completo-no-parcial.md``, sobre la clase única
``Domain``): **1** método (``validate``). **1 portado**, **0 ausentes**.

Correspondencia con la referencia (``odoo-tools@622ddc2a``)
===========================================================

===============================  ============================================
Referencia                       Aquí
===============================  ============================================
``Domain.validate`` (``:12``,    ``validate()`` — ``POST
``jsonrpc``, ``auth="user"``)    /api/v2/web/domain/validate/``
===============================  ============================================

Cómo se valida sin ``EXPLAIN`` — CONSTRUIDO, Rule 7
=====================================================

La referencia compila el dominio a SQL con ``Model.sudo()._search(domain)``
y lo envuelve en ``EXPLAIN`` para forzar al planificador a validarlo sin
ejecutarlo — su propio docstring descarta ``LIMIT 0`` porque "the semantics
of a falsy ``limit`` parameter... do not permit it" (un ``limit`` de Odoo
falsy significa "sin límite", no "cero filas").

Esa restricción es de **Odoo**, no de Django: aquí ``queryset[:0]`` es un
``LIMIT 0`` explícito e inequívoco (nunca "sin límite"), así que forzar su
evaluación (``list(...)``) hace que Postgres compile y planifique la
consulta sin traer filas — el mismo efecto que ``EXPLAIN`` perseguía, con la
primitiva que este stack sí tiene sin ambigüedad de por medio.

Dos divergencias declaradas
=============================

1. **``model`` usa la convención ``app_label.ModelName`` del proyecto**
   (≙ ``request.env[model]`` de la referencia), la misma que
   ``export.py::_get_model`` — no el ``dominio.punto`` de Odoo. Se reusa el
   mismo resolutor (no se duplica) — ``export.py`` documenta que Django no
   expone un ``request.env[model]`` genérico y por eso se construyó ahí.
2. **``domain`` se compila con ``osv.expression.to_q``** (≙ ``orm/domains.py``,
   la adaptación fiel del compilador de dominios de Odoo 19 — ver su
   docstring para el porte del AST) en vez de ``Model.sudo()._search()``: la
   referencia arma un objeto ``Query`` de su propio ORM; aquí ``to_q``
   entrega directamente el ``Q`` de Django que ``QuerySet.filter()`` consume.

Gate por capacidad, no por ``sudo()`` (DEC-11)
=================================================

La referencia usa ``Model.sudo()`` — bypass total de ACL, deliberado: validar
un dominio no debe fallar por permisos del usuario sobre el modelo, sólo por
sintaxis. Aquí no hay ACL por registro que evadir (DEC-11 gatea por
capacidad, no por fila); el equivalente es exigir la capacidad
``web.domain.validate`` en vez de ``sudo()`` — deliberadamente amplia (valida
contra cualquier modelo), mismo criterio que ``web.content.view``/
``web.export`` en este mismo addon.
"""
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from addons.authz.permissions import require_capability
from addons.web.controllers.export import _get_model
from addons.web.controllers.serializers import (
    DomainValidateRequestSerializer,
    DomainValidateResponseSerializer,
)
from osv.expression import to_q

#: ≙ ``web.content.view``/``web.export`` de este mismo addon — capacidad
#: deliberadamente amplia (valida contra cualquier modelo, sin dato que
#: exponer más allá de un booleano). Ver "Gate por capacidad" arriba.
_DOMAIN_VALIDATE_CAPABILITY = 'web.domain.validate'


@extend_schema(
    tags=['web'],
    summary='Validar un dominio contra un modelo',
    request=DomainValidateRequestSerializer,
    responses={
        200: DomainValidateResponseSerializer,
        400: DomainValidateResponseSerializer,
    },
)
@api_view(['POST'])
@require_capability(_DOMAIN_VALIDATE_CAPABILITY)
def validate(request):
    """≙ ``Domain.validate`` de la referencia — ``POST
    /api/v2/web/domain/validate/``.

    Parsea ``domain`` y verifica que se puede usar para buscar en ``model``.
    Devuelve ``{'valid': True}`` cuando el dominio es válido, ``{'valid':
    False}`` cuando no — mismo contrato que el booleano de la referencia,
    envuelto en objeto para llevar el nombre del campo en inglés
    (``identificadores-en-ingles.md``).

    :raises: nunca — un ``model`` inexistente responde 400 con
        ``codigo_error``, igual que el resto de vistas de este addon
        (``export.py::_export_response``); la referencia levanta
        ``ValidationError`` para el mismo caso.
    """
    payload = DomainValidateRequestSerializer(data=request.data)
    payload.is_valid(raise_exception=True)
    model_label = payload.validated_data['model']
    domain = payload.validated_data['domain']

    try:
        model = _get_model(model_label)
    except (LookupError, ValueError):
        return Response(
            {'codigo_error': 'INVALID_MODEL',
             'detail': f'Modelo desconocido: {model_label!r}.'},
            status=status.HTTP_400_BAD_REQUEST)

    try:
        # Ver "Cómo se valida sin EXPLAIN" arriba: LIMIT 0 fuerza la
        # compilación y planificación sin traer filas.
        list(model._default_manager.filter(to_q(domain, model))[:0])
        valid = True
    except Exception:  # pylint: disable=broad-except
        # ≙ referencia: "except Exception: return False" — cualquier fallo
        # de compilación o de planificación significa dominio inválido, no
        # un error del servidor.
        valid = False

    return Response({'valid': valid}, status=status.HTTP_200_OK)
