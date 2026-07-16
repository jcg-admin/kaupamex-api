"""Serializers — apps.modules.referral (UC-PRO-05)."""
from rest_framework import serializers


class ReferralStatusSerializer(serializers.Serializer):
    """Salida de GET /api/v1/account/referral/ — codigo + estadisticas."""
    code                = serializers.CharField(read_only=True)
    share_link          = serializers.CharField(read_only=True)
    total_referrals     = serializers.IntegerField(read_only=True)
    completed_referrals = serializers.IntegerField(read_only=True)
    rewards_earned      = serializers.IntegerField(read_only=True)


class RedeemReferralSerializer(serializers.Serializer):
    """Entrada de POST /api/v1/account/referral/redeem/."""
    code = serializers.CharField(max_length=50)
