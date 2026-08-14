"""Serializers de la superficie de pago del comprador — ``payment``."""
from rest_framework import serializers

from addons.payment.models import Payment


class InitiatePaymentSerializer(serializers.Serializer):
    """≙ el cuerpo de ``/payment/transaction``.

    ``token`` es opcional porque los métodos no-tarjeta (OXXO, SPEI) no lo
    llevan — la referencia hace la misma distinción en ``create_payment``.
    """

    order_number = serializers.CharField(max_length=64)
    token = serializers.CharField(max_length=255, required=False,
                                  allow_blank=True, default='')
    installments = serializers.IntegerField(required=False, default=1,
                                            min_value=1)
    payment_method_id = serializers.CharField(max_length=50, required=False,
                                              allow_blank=True, default='')
    issuer_id = serializers.CharField(max_length=50, required=False,
                                      allow_blank=True, default='')
    payer_email = serializers.EmailField(required=False, allow_blank=True,
                                         default='')


class PaymentSerializer(serializers.ModelSerializer):
    """Un intento de cobro.

    No expone ``gateway_payment_id`` ni ``preference_id``: son
    identificadores del proveedor y no le sirven al comprador, sólo amplían
    la superficie de lo que se filtra.
    """

    order_number = serializers.CharField(source='sale_order.name',
                                         read_only=True)

    class Meta:
        model = Payment
        fields = ['id', 'order_number', 'gateway', 'status', 'amount',
                  'installments', 'created_at']
        read_only_fields = fields
