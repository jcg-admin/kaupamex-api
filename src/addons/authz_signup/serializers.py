"""Serializers — addons.authz_signup."""
from rest_framework import serializers


class SignupSerializer(serializers.Serializer):
    """Alta externa (b2c) o set-password con token (≙ ``signup``).

    Con ``token`` → fija la contraseña del invitado. Sin ``token`` → alta
    externa (sólo si el signup público está abierto).
    """
    token = serializers.CharField(required=False, allow_blank=True, default='')
    login = serializers.EmailField(required=False, allow_blank=True,
                                   default='')
    name = serializers.CharField(required=False, allow_blank=True, default='')
    password = serializers.CharField(
        write_only=True, style={'input_type': 'password'})


class RequestResetSerializer(serializers.Serializer):
    login = serializers.CharField()
