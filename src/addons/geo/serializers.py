"""Serializers de la app geo (SEPOMEX).

Expone la consulta pública de código postal → asentamientos para el
autocompletado de direcciones (T-214, party). Un CP mapea a N asentamientos
(colonias) que comparten municipio y estado.
"""
from rest_framework import serializers

from addons.base_address_extended.models import CatalogPostalCode


class SettlementSerializer(serializers.ModelSerializer):
    """Un asentamiento (colonia) dentro de un CP."""

    class Meta:
        model = CatalogPostalCode
        fields = ['settlement_name', 'settlement_type']


class PostalCodeLookupSerializer(serializers.Serializer):
    """Respuesta agrupada de la consulta de un CP.

    Los campos municipio/estado/ciudad son comunes a todos los
    asentamientos del CP; ``settlements`` lista las colonias para que la UI
    ofrezca un selector.
    """

    postal_code = serializers.CharField()
    country = serializers.CharField()
    state = serializers.CharField()
    municipality = serializers.CharField()
    city = serializers.CharField()
    settlements = SettlementSerializer(many=True)
