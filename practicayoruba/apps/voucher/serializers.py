"""Serializers — apps.voucher (Sprint 13)."""
from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from .models import Voucher, VoucherChangeLog


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
        disc = getattr(obj, 'total_discount_given', None)
        rev  = getattr(obj, 'total_revenue_with_voucher', None)
        if not disc:
            return None
        try:
            return round(float(rev or 0) / float(disc), 2)
        except (ZeroDivisionError, TypeError):
            return None


class ApplyVoucherSerializer(serializers.Serializer):
    """POST /api/v1/cart/voucher/ — UC-CART-04."""
    code = serializers.CharField(max_length=50)
