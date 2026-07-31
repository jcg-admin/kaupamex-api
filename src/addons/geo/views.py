"""Vistas de la app geo (SEPOMEX).

Consulta pública de código postal → asentamientos para el autocompletado de
direcciones en checkout y perfil (T-214, party). Sólo lectura, ``AllowAny``:
la captura de dirección puede ocurrir en checkout anónimo.
"""
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.base_address_extended.models import CatalogPostalCode
from addons.geo.serializers import PostalCodeLookupSerializer


class PostalCodeLookupView(APIView):
    """``GET /api/v2/geo/postal-codes/<postal_code>/``.

    Devuelve municipio/estado/ciudad + la lista de asentamientos (colonias)
    del CP. 404 si el CP no existe en el catálogo. El país se filtra por el
    query param ``country`` (default ``MX``).
    """

    permission_classes = [AllowAny]

    def get(self, request, postal_code):
        country = request.query_params.get('country', 'MX')
        rows = list(
            CatalogPostalCode.objects
            .filter(country=country, postal_code=postal_code)
            .order_by('settlement_name')
        )
        if not rows:
            return Response(
                {'codigo_error': 'POSTAL_CODE_NOT_FOUND',
                 'detail': f'No hay asentamientos para el CP {postal_code}.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        first = rows[0]
        payload = {
            'postal_code': first.postal_code,
            'country': first.country,
            'state': first.state,
            'municipality': first.municipality,
            'city': first.city,
            'settlements': rows,
        }
        return Response(PostalCodeLookupSerializer(payload).data)
