"""
tokens.py — apps.users

TokenObtainPairView personalizada (FR-AUTH-02.07, FR-AUTH-02.09, FR-AUTH-02.15).

Extiende simplejwt para:
1. Normalizar el username a minúsculas antes de buscar (FR-AUTH-02.07)
2. Diferenciar error de email no verificado vs credenciales incorrectas (FR-AUTH-02.09)
3. Incluir objeto 'user' en la respuesta (FR-AUTH-02.15)
"""
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework import serializers as drf_serializers

User = get_user_model()


class PYTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Serializer de login con:
    - Normalización a minúsculas del username (FR-AUTH-02.07)
    - Error diferenciado para cuenta inactiva no verificada (FR-AUTH-02.09)
    - Respuesta con objeto user (FR-AUTH-02.15)
    """

    def validate(self, attrs):
        # FR-AUTH-02.07 — normalizar a minúsculas
        username = attrs.get(self.username_field, '').strip().lower()
        attrs[self.username_field] = username

        # FR-AUTH-02.09 — detectar usuario que existe pero no verificó email
        try:
            user = User.objects.get(username__iexact=username)
            if not user.is_active and user.has_usable_password():
                # La cuenta existe pero is_active=False (sin verificar)
                # y tiene password usable (no suspendida por admin de otra forma)
                raise AuthenticationFailed(
                    detail={
                        'codigo': 'EMAIL_NO_VERIFICADO',
                        'mensaje': (
                            'Tu cuenta aún no está activada. '
                            'Revisa tu email y haz clic en el enlace de verificación.'
                        ),
                    },
                    code='email_no_verificado',
                )
        except User.DoesNotExist:
            pass  # El error de credenciales incorrectas lo maneja simplejwt

        # Delegamos el flujo normal (verifica password, genera tokens)
        data = super().validate(attrs)

        # FR-AUTH-02.15 — añadir objeto user a la respuesta
        user = self.user
        data['user'] = {
            'id':         user.pk,
            'username':   user.username,
            'email':      user.email,
            'first_name': user.first_name,
            'last_name':  user.last_name,
            'is_staff':   user.is_staff,
            'avatar_url': user.get_avatar_url(),
        }
        return data


class PYTokenObtainPairView(TokenObtainPairView):
    """
    View de login personalizada.
    Sustituye a TokenObtainPairView estándar en urls.py.
    """
    serializer_class = PYTokenObtainPairSerializer
