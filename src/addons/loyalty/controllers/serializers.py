"""Serializers del programa de referidos — ``loyalty``."""
from rest_framework import serializers


class ReferralProgramSerializer(serializers.Serializer):
    """Mi código y el conteo de a quién he referido."""

    code = serializers.CharField(read_only=True)
    total = serializers.IntegerField(read_only=True)
    completed = serializers.IntegerField(read_only=True)


class RedeemReferralSerializer(serializers.Serializer):
    """El código que otro comprador me compartió."""

    code = serializers.CharField(max_length=50)
