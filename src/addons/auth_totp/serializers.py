"""Serializers — addons.auth_totp."""
from rest_framework import serializers


class TotpCodeSerializer(serializers.Serializer):
    """Un código TOTP de 6 dígitos (confirm / regenerar recovery)."""
    code = serializers.RegexField(r'^\d{6}$', help_text='Código de 6 dígitos.')


class TotpDisableSerializer(serializers.Serializer):
    """Código para desactivar el 2FA: un TOTP de 6 dígitos **o** un código de
    recuperación (un usuario que perdió el authenticator usa un backup)."""
    code = serializers.CharField(
        min_length=6, max_length=32, trim_whitespace=True,
        help_text='Código TOTP de 6 dígitos o un código de recuperación.',
    )
