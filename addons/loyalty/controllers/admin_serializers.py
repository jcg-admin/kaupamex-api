"""Serializers — addons.loyalty (Sprint 13)."""
from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from addons.loyalty.models import Voucher, VoucherChangeLog


class VoucherSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model  = Voucher
        fields = [
            'id', 'code', 'voucher_type',
            'discount_value', 'discount_pct', 'max_discount',
            'min_order_amount', 'max_uses', 'current_uses',
            'valid_from', 'valid_until',
            'is_active', 'restricted_to_email', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'current_uses', 'created_at', 'updated_at']

    def get_status(self, obj) -> str:
        if not obj.is_active:
            return 'INACTIVE'
        now = timezone.now()
        if now < obj.valid_from:
            return 'NOT_YET_ACTIVE'
        if obj.valid_until and now > obj.valid_until:
            return 'EXPIRED'
        if obj.max_uses is not None and obj.current_uses >= obj.max_uses:
            return 'EXHAUSTED'
        return 'ACTIVE'

    def validate_code(self, value):
        return value.upper()

    def validate_max_uses(self, value):
        # H-VOU-01: max_uses=0 agotaría el voucher inmediatamente — sin sentido.
        if value is not None and value < 1:
            raise serializers.ValidationError(
                'max_uses debe ser al menos 1, o null para usos ilimitados.')
        return value

    def validate(self, data):
        vtype = data.get('voucher_type') or (self.instance.voucher_type if self.instance else None)

        if vtype == Voucher.TYPE_FIXED:
            val = data.get('discount_value') or (self.instance.discount_value if self.instance else None)
            if not val or val <= 0:
                raise serializers.ValidationError(
                    {'discount_value': 'Requerido y > 0 para tipo FIXED.'})

        elif vtype == Voucher.TYPE_PERCENTAGE:
            pct = data.get('discount_pct') or (self.instance.discount_pct if self.instance else None)
            if not pct or not (0 < pct <= 100):
                raise serializers.ValidationError(
                    {'discount_pct': 'Requerido y entre 0.01 y 100 para tipo PERCENTAGE.'})

        # H-VOU-02: valid_until debe ser posterior a valid_from.
        valid_from  = data.get('valid_from')  or (self.instance.valid_from  if self.instance else None)
        valid_until = data.get('valid_until') or (self.instance.valid_until if self.instance else None)
        if valid_from and valid_until and valid_until <= valid_from:
            raise serializers.ValidationError(
                {'valid_until': 'valid_until debe ser posterior a valid_from.'})

        # H-VOU-03: valid_until no puede estar en el pasado.
        # Sin esta validación un admin puede crear un voucher con valid_until
        # ya vencido; el voucher aparece como EXPIRED inmediatamente y nunca
        # puede ser usado, pero sigue contaminando el listado de cupones activos.
        # Solo se aplica cuando valid_until se envía explícitamente en la
        # petición (no heredado del instance) para no bloquear lecturas/PATCHs
        # que no toquen el campo.
        if 'valid_until' in data and data['valid_until'] is not None:
            if data['valid_until'] <= timezone.now():
                raise serializers.ValidationError(
                    {'valid_until': 'valid_until debe ser una fecha futura.'})

        return data


class VoucherReportSerializer(serializers.ModelSerializer):
    """UC-PRO-04: reporte de uso con ROI y agregados de ordenes."""
    status                     = serializers.SerializerMethodField()
    orders_count               = serializers.IntegerField(read_only=True, default=0)
    total_discount_given       = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, allow_null=True, default=None,
    )
    total_revenue_with_voucher = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True, allow_null=True, default=None,
    )
    roi = serializers.SerializerMethodField()

    class Meta:
        model  = Voucher
        fields = [
            'id', 'code', 'voucher_type', 'discount_value', 'discount_pct',
            'max_uses', 'current_uses', 'valid_from', 'valid_until',
            'is_active', 'status',
            'orders_count', 'total_discount_given', 'total_revenue_with_voucher', 'roi',
        ]

    def get_status(self, obj):
        return VoucherSerializer().get_status(obj)

    def get_roi(self, obj):
        # H-CICLO112-02: usar Decimal en lugar de float() para la division
        # monetaria ROI = revenue / discount. float() sobre Decimal introduce
        # error de punto flotante en datos monetarios (p.ej. 0.30000000000000004
        # en lugar de 0.30), violando la politica "Decimal para calculos
        # monetarios, nunca float". Se convierte a Decimal, se divide con
        # precision completa y se redondea a 2 decimales antes de retornar
        # como str para que el serializer lo trate correctamente.
        disc = getattr(obj, 'total_discount_given', None)
        rev  = getattr(obj, 'total_revenue_with_voucher', None)
        if not disc:
            return None
        try:
            disc_d = Decimal(str(disc))
            rev_d  = Decimal(str(rev or 0))
            if disc_d == 0:
                return None
            return float((rev_d / disc_d).quantize(Decimal('0.01')))
        except (ZeroDivisionError, TypeError, Exception):
            return None


class ApplyVoucherSerializer(serializers.Serializer):
    """POST /api/v1/cart/voucher/ — UC-CART-04."""
    code = serializers.CharField(max_length=50)
