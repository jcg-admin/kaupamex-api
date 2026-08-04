"""Serializers — consulta pública de código postal.

La respuesta **no** es la fila del modelo: es el CP agrupado. ``CatalogPostalCode``
guarda una fila por asentamiento, y el consumidor (el formulario de dirección)
necesita lo contrario — los datos comunes una vez y la lista de asentamientos
para poblar el selector. Por eso hay dos serializers y no un ``ModelSerializer``
sobre el queryset.
"""
from rest_framework import serializers


class SettlementSerializer(serializers.Serializer):
    """Un asentamiento dentro del CP — lo que el selector ofrece."""

    settlement_name = serializers.CharField(read_only=True)
    settlement_type = serializers.CharField(read_only=True)
    settlement_consecutive_id = serializers.CharField(read_only=True)
    zone = serializers.CharField(read_only=True)


class PostalCodeLookupSerializer(serializers.Serializer):
    """El CP resuelto: lo común una vez, los asentamientos como lista."""

    postal_code = serializers.CharField(read_only=True)
    country = serializers.CharField(read_only=True)
    state = serializers.CharField(read_only=True)
    state_code = serializers.CharField(read_only=True)
    municipality = serializers.CharField(read_only=True)
    city = serializers.CharField(read_only=True)
    settlements = SettlementSerializer(many=True, read_only=True)
