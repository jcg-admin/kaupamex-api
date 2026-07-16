"""Serializers — apps.finance (UC-FIN-06 CashConcept, UC-FIN-01 settlements)."""
from rest_framework import serializers

from apps.finance.exceptions import DuplicateCode, ImmutableField
from apps.finance.models import (
    CarrierInvoice, CashConcept, GatewaySettlement, GatewaySettlementLine,
)


class CashConceptSerializer(serializers.ModelSerializer):
    """Serializer del catalogo de conceptos (UC-FIN-06).

    - ``code`` y ``kind`` son inmutables en update -> ``IMMUTABLE_FIELD`` (422).
    - ``code`` duplicado en create -> ``DUPLICATE_CODE`` (409).
    """

    # Declaracion explicita para NO heredar el UniqueValidator automatico del
    # modelo (que devolveria 400): la unicidad se maneja en validate_code para
    # emitir el codigo canonico DUPLICATE_CODE (409, UC-FIN-06 EX-02).
    code = serializers.CharField(max_length=64)

    class Meta:
        model = CashConcept
        fields = [
            'id', 'code', 'name', 'kind', 'parent', 'account',
            'editable', 'leaf', 'active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_code(self, value):
        # Unicidad explicita para devolver el codigo canonico DUPLICATE_CODE en
        # create (en update el code es inmutable, se maneja abajo).
        if self.instance is None and CashConcept.objects.filter(code=value).exists():
            raise DuplicateCode(value)
        return value

    def update(self, instance, validated_data):
        # code y kind son inmutables una vez creado el concepto (UC-FIN-06 EX-04).
        for field in ('code', 'kind'):
            if field in validated_data and validated_data[field] != getattr(instance, field):
                raise ImmutableField(field)
            validated_data.pop(field, None)
        return super().update(instance, validated_data)


class GatewaySettlementLineSerializer(serializers.ModelSerializer):
    """Linea de una liquidacion (UC-FIN-01)."""

    class Meta:
        model = GatewaySettlementLine
        fields = ['id', 'flag', 'amount']


class GatewaySettlementSerializer(serializers.ModelSerializer):
    """Liquidacion del gateway con sus lineas (UC-FIN-01)."""
    lines = GatewaySettlementLineSerializer(many=True, read_only=True)

    class Meta:
        model = GatewaySettlement
        fields = [
            'id', 'adapter', 'gateway_ref', 'gross', 'fee', 'net',
            'settled_at', 'status', 'payment', 'lines',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'updated_at']


class CarrierInvoiceSerializer(serializers.ModelSerializer):
    """Flete por pagar al transportista (UC-FIN-03)."""

    class Meta:
        model = CarrierInvoice
        fields = [
            'id', 'carrier', 'gross', 'free_shipping_subsidy',
            'status', 'paid_at', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'status', 'paid_at', 'created_at', 'updated_at']
