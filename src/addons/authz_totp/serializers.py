"""Serializers — addons.authz_totp."""
from rest_framework import serializers


class TotpCodeSerializer(serializers.Serializer):
    """Un código TOTP de 6 dígitos (confirm / disable)."""
    code = serializers.RegexField(r'^\d{6}$', help_text='Código de 6 dígitos.')
