"""Serializers — addons.authz_totp."""
from rest_framework import serializers


class TotpCodeSerializer(serializers.Serializer):
    """Un código TOTP de 6 dígitos (confirm / regenerar recovery)."""
    code = serializers.RegexField(r'^\d{6}$', help_text='Código de 6 dígitos.')


class TotpLoginSerializer(serializers.Serializer):
    """El segundo paso del login — ≙ los dos ``kwargs`` de ``web_totp``.

    ``code`` es ``totp_token`` de la referencia (``auth_totp/controllers/
    home.py:41``), con una divergencia declarada: allá el campo se lee como
    ``int(re.sub(r'\\s', '', ...))`` y sólo admite el código de la app; aquí
    admite **también** un código de recuperación, porque este árbol los tiene
    como mecanismo propio (``TotpRecoveryCode``) y la referencia no. Por eso el
    tipo es ``CharField`` y no un patrón de seis dígitos: el de recuperación es
    más largo.

    ``remember`` es ``kwargs.get('remember')`` (``:59``) — la casilla que pide
    recordar este navegador y que dispara la cookie ``td_id``.
    """
    code = serializers.CharField(
        min_length=6, max_length=32, trim_whitespace=True,
        help_text='Código TOTP de 6 dígitos o un código de recuperación.',
    )
    remember = serializers.BooleanField(
        required=False, default=False,
        help_text='Recordar este navegador y no volver a pedir el segundo factor.',
    )


class TotpDisableSerializer(serializers.Serializer):
    """Código para desactivar el 2FA: un TOTP de 6 dígitos **o** un código de
    recuperación (un usuario que perdió el authenticator usa un backup)."""
    code = serializers.CharField(
        min_length=6, max_length=32, trim_whitespace=True,
        help_text='Código TOTP de 6 dígitos o un código de recuperación.',
    )
