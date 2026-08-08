"""Consulta pública de código postal — ``GET /api/v2/geo/postal-codes/<cp>/``.

Forma propia, declarada
========================

**La referencia no cubre esto.** Medido sobre ``odoo-tools@622ddc2a``:
``odoo19c: addons/base_address_extended/`` y ``addons/base_geolocalize/`` no
tienen ``controllers/``, y no existe ninguna ``@route`` cuyo path contenga
``zip``/``postal`` en todo el árbol. Odoo captura el código postal como texto
libre en ``res.partner.zip`` y resuelve la ciudad con ``res.city``; no ofrece
un servicio de resolución CP → asentamientos.

Esto **no** es un puerto: es superficie propia sobre un catálogo propio
(SEPOMEX para MX). Se declara aquí para que nadie la lea como adaptación —
``referencia-odoo-gobierna-las-decisiones`` exige decirlo antes de proponer, y
una propuesta inventada presentada como derivada es el defecto que esa regla
persigue.

Lo que sí hereda del árbol es la **forma del endpoint**, no su existencia: FBV
con ``@extend_schema``, ``codigo_error`` en el cuerpo de error, y ``AllowAny``
porque la captura de dirección ocurre en checkout anónimo.
"""
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from addons.base_address_extended.controllers.serializers import (
    PostalCodeLookupSerializer,
)
from addons.base_address_extended.models import CatalogPostalCode

DEFAULT_COUNTRY = 'MX'


@extend_schema(
    tags=['geo'],
    summary='Resolver un código postal en municipio, estado y asentamientos',
    parameters=[
        OpenApiParameter(
            'country', str,
            description='ISO 3166-1 alpha-2. Por defecto MX. El mismo CP '
                        'existe en países distintos.'),
    ],
    responses={
        200: PostalCodeLookupSerializer,
        404: OpenApiResponse(description='POSTAL_CODE_NOT_FOUND'),
    },
    auth=[],
)
@api_view(['GET'])
@permission_classes([AllowAny])
def postal_code_lookup(request, postal_code):
    """CP → sus asentamientos, agrupados.

    El catálogo guarda una fila por asentamiento; el consumidor necesita lo
    contrario. Los campos comunes (estado, municipio, ciudad) se toman de la
    primera fila: son los mismos para todo el CP dentro de un país — es la
    estructura del propio catálogo, no un supuesto de esta vista.
    """
    country = request.query_params.get('country') or DEFAULT_COUNTRY
    rows = list(
        CatalogPostalCode.objects
        .filter(postal_code=postal_code, country=country)
        .order_by('settlement_name')
    )
    if not rows:
        return Response(
            {'codigo_error': 'POSTAL_CODE_NOT_FOUND',
             'detail': f'No hay asentamientos para el CP {postal_code} '
                       f'en {country}.'},
            status=status.HTTP_404_NOT_FOUND)

    head = rows[0]
    return Response({
        'postal_code': head.postal_code,
        'country': head.country,
        'state': head.state,
        'state_code': head.state_code,
        'municipality': head.municipality,
        'city': head.city,
        'settlements': [
            {
                'settlement_name': r.settlement_name,
                'settlement_type': r.settlement_type,
                'settlement_consecutive_id': r.settlement_consecutive_id,
                'zone': r.zone,
            }
            for r in rows
        ],
    })
