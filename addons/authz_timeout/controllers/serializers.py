"""Serializers — ``addons.authz_timeout``.

La fuente no tiene serializers: su ruta ``jsonrpc`` recibe ``**kwargs`` sin
validar y deja que ``_check_identity`` reviente si el token no es numérico
(``int(re.sub(r"\\s", "", credential["token"]))``, ``ir_http.py:102``). Aquí
esa validación se adelanta al serializer, que es donde DRF la sella como
**400** en vez de dejarla salir como 500.
"""
import re

from rest_framework import serializers

#: Los cuatro tipos que ``_check_credential`` despacha — el mismo vocabulario
#: que ``_get_auth_methods`` devuelve (``models/res_users.py``).
CREDENTIAL_TYPES = ('password', 'totp', 'totp_mail', 'webauthn')

#: Los dos que la fuente normaliza a entero antes de verificar.
NUMERIC_TYPES = ('totp', 'totp_mail')


class CheckIdentitySerializer(serializers.Serializer):
    """La credencial con que el usuario confirma su identidad.

    Todos los campos son opcionales porque el cuerpo vacío es un caso
    legítimo del contrato: la fuente devuelve el catálogo de métodos cuando
    ``not credential`` (``ir_http.py:98``).
    """

    type = serializers.ChoiceField(choices=CREDENTIAL_TYPES, required=False)
    password = serializers.CharField(required=False, allow_blank=True,
                                     trim_whitespace=False, write_only=True)
    token = serializers.CharField(required=False, allow_blank=True,
                                  write_only=True)

    def validate(self, attrs):
        tipo = attrs.get('type')
        if tipo in NUMERIC_TYPES:
            crudo = re.sub(r'\s', '', str(attrs.get('token') or ''))
            if not crudo.isdigit():
                raise serializers.ValidationError({
                    'codigo_error': 'INVALID_TOKEN',
                    'detail': 'El código debe ser numérico.',
                })
            attrs['token'] = crudo
        elif tipo == 'password' and not attrs.get('password'):
            raise serializers.ValidationError({
                'codigo_error': 'INVALID_CREDENTIAL',
                'detail': 'Falta la contraseña.',
            })
        return attrs
