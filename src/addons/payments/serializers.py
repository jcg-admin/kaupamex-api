"""Serializers — addons.payments (Sprint 15). Compatible con drf-spectacular."""
from decimal import Decimal
from rest_framework import serializers
from addons.payment.models import Payment, Refund, Chargeback, PaymentGatewayEvent, SavedCard
from .gateways.mercadopago import NON_CARD_METHOD_IDS



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
    """POST /api/v2/payments/initiate/ (deprecated) — use /mercadopago/ instead.

    Generic endpoint kept for UI backwards-compat (OBS-U1). Accepts an
    explicit `gateway` field in the body. New integrations should use the
    gateway-specific URL (/mercadopago/) where the gateway is implied.
    PayPal endpoint is not exposed — see DEC-PAY-01 in payments/urls.py.
    """
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


class MercadoPagoInitiateSerializer(serializers.Serializer):
    """POST /api/v2/payments/mercadopago/ — UC-PAY-01 (F6 Tier B, GAP-I1).

    Gateway-specific endpoint: MercadoPago is implied by the URL so the
    `gateway` field is absent. Preferred over the generic /initiate/ for
    new integrations.
    """
    order_number  = serializers.CharField(
        max_length=20,
        help_text='Número de orden a pagar (PY-XXXXXXXX).',
    )
    installments  = serializers.IntegerField(
        default=1, min_value=1,
        help_text='Número de cuotas MSI. 1 = contado (sin interés).',
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
    """Respuesta de GET /api/v2/payments/installments/"""
    order_number = serializers.CharField()
    amount       = serializers.DecimalField(max_digits=10, decimal_places=2)
    plans        = InstallmentPlanSerializer(many=True)


class PaymentReturnSerializer(serializers.Serializer):
    """Query params del retorno del gateway — GET /api/v2/payments/<order>/return/"""
    status             = serializers.CharField(required=False, default='pending', max_length=50)
    payment_id         = serializers.CharField(required=False, allow_blank=True, max_length=100)
    external_reference = serializers.CharField(required=False, allow_blank=True, max_length=100)


class CheckoutEligibilitySerializer(serializers.Serializer):
    """Respuesta de GET /api/v2/checkout/eligibility/"""
    express_available    = serializers.BooleanField()
    reason               = serializers.CharField(allow_null=True)
    default_address      = serializers.DictField(allow_null=True)
    default_shipping     = serializers.DictField(allow_null=True)
    estimated_total      = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True,
    )


class ExpressCheckoutSerializer(serializers.Serializer):
    """POST /api/v2/checkout/express/ — UC-ORD-01-EXT."""
    notes        = serializers.CharField(
        required=False, default='', allow_blank=True, max_length=1000,
    )
    installments = serializers.IntegerField(
        default=1, min_value=1,
        help_text='Número de cuotas. 1 = contado.',
    )


class PaymentStatusSerializer(serializers.Serializer):
    """Respuesta de GET /api/v2/payments/<order>/status/ — UC-PAY-05."""
    order_number    = serializers.CharField()
    order_status    = serializers.CharField()
    payment_status  = serializers.CharField()
    gateway         = serializers.CharField(allow_null=True)
    amount          = serializers.DecimalField(
        max_digits=10, decimal_places=2, allow_null=True)
    created_at      = serializers.DateTimeField(allow_null=True)


class RefundRequestSerializer(serializers.Serializer):
    """POST /api/v2/payments/<order>/refund/ — UC-PAY-07."""
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


class ChargebackSerializer(serializers.ModelSerializer):
    """Admin chargeback representation. T-17-B, T-17-C."""

    class Meta:
        model  = Chargeback
        fields = [
            'id', 'gateway_chargeback_id', 'gateway_payment_id',
            'amount', 'status', 'reason_code', 'description', 'created_at',
        ]
        read_only_fields = fields


class RetryEligibilitySerializer(serializers.Serializer):
    """Respuesta de GET /api/v2/payments/<order>/retry-eligibility/ — UC-PAY-08."""
    eligible             = serializers.BooleanField()
    order_number         = serializers.CharField(allow_null=True)
    order_status         = serializers.CharField(allow_null=True)
    last_failed_gateway  = serializers.CharField(allow_null=True)
    available_gateways   = serializers.ListField(
        child=serializers.CharField(), allow_null=True)
    reason               = serializers.CharField(allow_null=True)
    codigo_error         = serializers.CharField(allow_null=True)


# =============================================================================
# Checkout API v2 — ADR-018 (pago en sitio sin redirección)
# =============================================================================

class CheckoutApiPaymentSerializer(serializers.Serializer):
    """POST /api/v2/payments/initiate/ — Checkout API (ADR-018).

    Soporta métodos de tarjeta (token obligatorio) y métodos sin tarjeta
    (OXXO, SPEI, cajeros, Cuenta MP) donde token se omite.
    BR-009: el token es de un solo uso y solo se envía al backend.
    """
    order_number    = serializers.CharField(max_length=20)
    token           = serializers.CharField(
        max_length=255, required=False, allow_blank=True,
        help_text='Token de tarjeta generado por CardForm (caduca en 7 min). '
                  'Requerido para métodos de tarjeta; omitir para OXXO/SPEI/cajeros.',
    )
    installments    = serializers.IntegerField(
        default=1, min_value=1,
        help_text='Número de cuotas. 1 = contado. Ignorado en métodos no-tarjeta.',
    )
    payment_method_id = serializers.CharField(
        max_length=50,
        help_text='ID del método de pago: "visa", "master", "oxxo", "clabe", etc.',
    )
    issuer_id       = serializers.CharField(
        max_length=50, required=False, allow_blank=True,
        help_text='ID del banco emisor. Opcional pero mejora la tasa de aprobación.',
    )
    payer_email     = serializers.EmailField(
        required=False, allow_blank=True,
        help_text='Email del pagador. Fallback: email del usuario autenticado.',
    )
    payer_identification_type = serializers.CharField(
        max_length=20, required=False, allow_blank=True,
        help_text='Tipo de documento ("CURP", "RFC", …).',
    )
    payer_identification_number = serializers.CharField(
        max_length=50, required=False, allow_blank=True,
        help_text='Número de documento del pagador.',
    )
    expected_amount = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        help_text='Monto visto por el cliente. Si difiere del total → 422 AMOUNT_MISMATCH.',
    )

    def validate(self, attrs):
        method_id = attrs.get('payment_method_id', '')
        token     = attrs.get('token', '')
        if method_id not in NON_CARD_METHOD_IDS and not token:
            raise serializers.ValidationError(
                {'token': 'Requerido para métodos de tarjeta.'}
            )
        return attrs


class CheckoutApiResponseSerializer(serializers.Serializer):
    """Respuesta de POST /api/v2/payments/initiate/ — Checkout API.

    Incluye campos para métodos no-tarjeta:
      external_resource_url — URL del voucher/barcode (OXXO, Paycash, cajeros)
      date_of_expiration    — fecha límite de pago (OXXO, SPEI, cajeros)
      transaction_data      — CLABE (SPEI) u otros datos de la transacción
    """
    payment_id              = serializers.IntegerField(allow_null=True)
    gateway_payment_id      = serializers.CharField(
        help_text='ID del pago en MercadoPago.',
    )
    status                  = serializers.CharField(
        help_text='Estado MP: approved | rejected | pending | in_process.',
    )
    status_detail           = serializers.CharField(
        help_text='Detalle: accredited, cc_rejected_insufficient_amount, etc.',
    )
    order_number            = serializers.CharField()
    amount                  = serializers.DecimalField(max_digits=10, decimal_places=2)
    installments            = serializers.IntegerField()
    external_resource_url   = serializers.CharField(
        allow_blank=True, default='',
        help_text='URL del voucher/barcode para pago en efectivo o cajero.',
    )
    date_of_expiration      = serializers.CharField(
        allow_blank=True, default='',
        help_text='Fecha límite de pago ISO-8601 (OXXO, SPEI, cajeros).',
    )
    transaction_data        = serializers.DictField(
        allow_null=True, default=None,
        help_text='Datos adicionales: CLABE (SPEI), barcode data (ATM/OXXO), etc.',
    )


class MpPublicKeySerializer(serializers.Serializer):
    """Respuesta de GET /api/v2/payments/public-key/."""
    public_key = serializers.CharField(
        help_text='Public key de MercadoPago para inicializar MP.js en el frontend. '
                  'BR-009: esta clave SÍ puede ir al frontend; el access_token NUNCA.',
    )


# =============================================================================
# Customer Card Management serializers
# =============================================================================

class MpSaveCardSerializer(serializers.Serializer):
    """POST /api/v2/payments/cards/ — guarda una nueva tarjeta."""
    token = serializers.CharField(
        max_length=255,
        help_text='Token generado por CardForm de MP.js (un solo uso, caduca en 7 min).',
    )


class MpCardPaymentMethodSerializer(serializers.Serializer):
    id               = serializers.CharField(allow_blank=True, default='')
    name             = serializers.CharField(allow_blank=True, default='')
    payment_type_id  = serializers.CharField(allow_blank=True, default='')
    thumbnail        = serializers.CharField(allow_blank=True, default='')
    secure_thumbnail = serializers.CharField(allow_blank=True, default='')


class MpCardSerializer(serializers.Serializer):
    """Representación de una tarjeta guardada (respuesta de cards API)."""
    id                = serializers.CharField()
    expiration_month  = serializers.IntegerField()
    expiration_year   = serializers.IntegerField()
    first_six_digits  = serializers.CharField(allow_blank=True, default='')
    last_four_digits  = serializers.CharField()
    payment_method    = MpCardPaymentMethodSerializer(allow_null=True, required=False)
    cardholder_name   = serializers.CharField(
        source='cardholder.name', allow_blank=True, default='',
    )
    status            = serializers.CharField()


class MpUpdateCardSerializer(serializers.Serializer):
    """PUT /api/v2/payments/cards/{id}/ — actualiza datos de una tarjeta."""
    expiration_month  = serializers.IntegerField(min_value=1, max_value=12, required=False)
    expiration_year   = serializers.IntegerField(min_value=2024, required=False)
    cardholder_name   = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                'Debe proporcionar al menos un campo para actualizar.'
            )
        return attrs


class ZeroDollarAuthSerializer(serializers.Serializer):
    """POST /api/v2/payments/cards/validate/ — T-15 Zero Dollar Auth."""
    token             = serializers.CharField(max_length=255)
    payment_method_id = serializers.CharField(max_length=50)
