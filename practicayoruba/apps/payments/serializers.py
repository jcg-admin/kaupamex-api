"""Serializers — apps.payments (Sprint 15). Compatible con drf-spectacular."""
from decimal import Decimal
from rest_framework import serializers

from .models import Payment, Refund, PaymentGatewayEvent


class PaymentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model  = Payment
        fields = [
            'id', 'order_number', 'gateway', 'status',
            'amount', 'installments', 'preference_id',
            'gateway_payment_id', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class InitiatePaymentSerializer(serializers.Serializer):
    """POST /api/v1/payments/initiate/ — UC-PAY-01."""
    order_number  = serializers.CharField(
        max_length=20,
        help_text='Número de orden a pagar (PY-XXXXXXXX).',
    )
    installments  = serializers.IntegerField(
        default=1, min_value=1,
        help_text='Número de cuotas MSI. 1 = contado (UC-PAY-01). >1 = cuotas (UC-PAY-01-EXT).',
    )


class InitiatePaymentResponseSerializer(serializers.Serializer):
    """Respuesta de POST /api/v1/payments/initiate/."""
    payment_id   = serializers.IntegerField()
    checkout_url = serializers.URLField(
        help_text='URL de la interfaz de pago del gateway. El frontend redirige al comprador aquí.',
    )
    order_number = serializers.CharField()
    amount       = serializers.DecimalField(max_digits=10, decimal_places=2)
    installments = serializers.IntegerField()


class InstallmentPlanSerializer(serializers.Serializer):
    """Un plan de cuotas MSI disponible."""
    installments            = serializers.IntegerField()
    amount_per_installment  = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_amount            = serializers.DecimalField(max_digits=10, decimal_places=2)
    interest_rate           = serializers.DecimalField(max_digits=5, decimal_places=2)


class InstallmentPlansResponseSerializer(serializers.Serializer):
    """Respuesta de GET /api/v1/payments/installments/"""
    order_number = serializers.CharField()
    amount       = serializers.DecimalField(max_digits=10, decimal_places=2)
    plans        = InstallmentPlanSerializer(many=True)


class PaymentReturnSerializer(serializers.Serializer):
    """Query params del retorno del gateway — GET /api/v1/payments/<order>/return/"""
    status             = serializers.CharField(required=False, default='pending')
    payment_id         = serializers.CharField(required=False, allow_blank=True)
    external_reference = serializers.CharField(required=False, allow_blank=True)


class CheckoutEligibilitySerializer(serializers.Serializer):
    """Respuesta de GET /api/v1/checkout/eligibility/"""
    express_available    = serializers.BooleanField()
    reason               = serializers.CharField(allow_null=True)
    default_address      = serializers.DictField(allow_null=True)
    default_shipping     = serializers.DictField(allow_null=True)
    estimated_total      = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )


class ExpressCheckoutSerializer(serializers.Serializer):
    """POST /api/v1/checkout/express/ — UC-ORD-01-EXT."""
    notes        = serializers.CharField(
        required=False, default='', allow_blank=True,
    )
    installments = serializers.IntegerField(
        default=1, min_value=1,
        help_text='Número de cuotas. 1 = contado.',
    )
