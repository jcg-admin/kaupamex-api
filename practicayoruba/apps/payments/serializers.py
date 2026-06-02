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


class AdminPaymentSerializer(PaymentSerializer):
    """Admin-only payment representation.

    Extends the public PaymentSerializer with order context fields that
    the admin panel needs to display without a separate order request:
    order_status and user_email.  Using the public PaymentSerializer in
    AdminPaymentDetailView left the admin panel without these fields,
    forcing the UI to either show blanks or issue an extra request.
    """

    order_status = serializers.CharField(source='order.status', read_only=True)
    user_email   = serializers.SerializerMethodField()

    class Meta(PaymentSerializer.Meta):
        fields = PaymentSerializer.Meta.fields + ['order_status', 'user_email']
        read_only_fields = fields

    def get_user_email(self, obj) -> str | None:
        return obj.order.user.email if obj.order.user_id else obj.order.guest_email


class InitiatePaymentSerializer(serializers.Serializer):
    """POST /api/v1/payments/initiate/ — UC-PAY-01 (MP) y UC-PAY-02 (PayPal)."""
    GATEWAY_CHOICES = [('MERCADOPAGO', 'MercadoPago'), ('PAYPAL', 'PayPal')]

    order_number  = serializers.CharField(
        max_length=20,
        help_text='Número de orden a pagar (PY-XXXXXXXX).',
    )
    gateway       = serializers.ChoiceField(
        choices=GATEWAY_CHOICES,
        default='MERCADOPAGO',
        help_text='Gateway de pago. MERCADOPAGO (por defecto, BR-006) o PAYPAL (BR-007).',
    )
    installments  = serializers.IntegerField(
        default=1, min_value=1,
        help_text='Número de cuotas MSI. Solo aplica para MERCADOPAGO. 1 = contado.',
    )
    expected_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        help_text='UC-PAY-01 AC-06: monto visto por el cliente en el checkout. '
                  'Si difiere del total recalculado de la orden → 422 '
                  'AMOUNT_MISMATCH.',
    )


class InitiatePaymentResponseSerializer(serializers.Serializer):
    """Respuesta de POST /api/v1/payments/initiate/.

    payment_id is deprecated (always null).  Use order_number to poll
    /payments/<order_number>/status/ — RNF-SEC-001 forbids exposing
    sequential internal PKs.
    """
    payment_id   = serializers.IntegerField(allow_null=True, required=False)
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
    status             = serializers.CharField(required=False, default='pending', max_length=50)
    payment_id         = serializers.CharField(required=False, allow_blank=True, max_length=100)
    external_reference = serializers.CharField(required=False, allow_blank=True, max_length=100)


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
        required=False, default='', allow_blank=True, max_length=1000,
    )
    installments = serializers.IntegerField(
        default=1, min_value=1,
        help_text='Número de cuotas. 1 = contado.',
    )


class PaymentStatusSerializer(serializers.Serializer):
    """Respuesta de GET /api/v1/payments/<order>/status/ — UC-PAY-05."""
    order_number    = serializers.CharField()
    order_status    = serializers.CharField()
    payment_status  = serializers.CharField()
    gateway         = serializers.CharField(allow_null=True)
    amount          = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True)
    created_at      = serializers.DateTimeField(allow_null=True)


class RefundRequestSerializer(serializers.Serializer):
    """POST /api/v1/payments/<order>/refund/ — UC-PAY-07."""
    amount = serializers.DecimalField(
        max_digits=10, decimal_places=2,
        required=False, allow_null=True,
        help_text='Monto a reembolsar. Null o ausente = reembolso total.',
    )
    reason = serializers.CharField(
        required=False, default='', allow_blank=True, max_length=500,
        help_text='Motivo del reembolso.',
    )


class RefundSerializer(serializers.ModelSerializer):
    """Buyer-facing refund representation. Does not expose gateway internals."""

    payment_id = serializers.IntegerField(source='payment.pk', read_only=True)

    class Meta:
        model  = Refund
        fields = ['id', 'payment_id', 'amount', 'reason', 'status', 'created_at']
        read_only_fields = fields


class AdminRefundSerializer(RefundSerializer):
    """Admin-only refund representation. Includes gateway_refund_id."""

    class Meta(RefundSerializer.Meta):
        fields = RefundSerializer.Meta.fields + ['gateway_refund_id']
        read_only_fields = fields


class RetryEligibilitySerializer(serializers.Serializer):
    """Respuesta de GET /api/v1/payments/<order>/retry-eligibility/ — UC-PAY-08."""
    eligible             = serializers.BooleanField()
    order_number         = serializers.CharField(allow_null=True)
    order_status         = serializers.CharField(allow_null=True)
    last_failed_gateway  = serializers.CharField(allow_null=True)
    available_gateways   = serializers.ListField(
        child=serializers.CharField(), allow_null=True)
    reason               = serializers.CharField(allow_null=True)
    codigo_error         = serializers.CharField(allow_null=True)
