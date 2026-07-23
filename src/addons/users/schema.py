"""
schema.py — addons.users

Extensiones de drf-spectacular para documentar correctamente los
endpoints de autenticación de PracticaYoruba.

Patron: blueprints de drf-spectacular (ver /tmp/references/drf-spectacular/docs/blueprints.rst)
Importado desde UsersConfig.ready() para que se registre al iniciar Django.

Problema que resuelve:
  PYTokenObtainPairSerializer hereda de TokenObtainPairSerializer pero
  añade un campo 'user' a la respuesta. La extension built-in de
  drf-spectacular para simplejwt solo documenta {access, refresh} y no
  conoce el campo extra. El resultado en Swagger era "No response body"
  para el login.

  Lo mismo ocurre con todos los endpoints que retornan solo un
  {'message': '...'} — drf-spectacular no genera un schema para ellos
  porque no hay un Serializer declarado.

Patron seguido: IACT-api/apps/users/viewsets_openapi_completion.py
"""

# ─────────────────────────────────────────────────────────────────────
# SPECTACULAR_TAGS
# Recogidas automáticamente por config.spectacular_hooks.collect_app_tags
# ─────────────────────────────────────────────────────────────────────
SPECTACULAR_TAGS = [
    {
        'name': 'auth',
        'description': (
            'Autenticación y ciclo de vida de la sesión: registro, login, '
            'logout, renovación de token, recuperación de contraseña y '
            'verificación de email.'
        ),
    },
    {
        'name': 'admin',
        'description': (
            'Gestión de usuarios del backoffice (solo administradores): '
            'listado, perfil, suspensión, reactivación y creación de cuentas '
            'de operaciones.'
        ),
    },
    {
        'name': 'profile',
        'description': (
            'Perfil, avatar y direcciones del comprador autenticado.'
        ),
    },
]



from drf_spectacular.authentication import SessionScheme
from drf_spectacular.extensions import OpenApiSerializerExtension, OpenApiViewExtension
from drf_spectacular.utils import inline_serializer, extend_schema, OpenApiResponse
from rest_framework import serializers


class CsrfExemptSessionScheme(SessionScheme):
    """Documenta la auth por sesion (ADR-018) en el esquema OpenAPI.

    Tras la migracion, ``CsrfExemptSessionAuthentication`` es la auth por
    defecto. drf-spectacular no resuelve subclases de ``SessionAuthentication``
    automaticamente (solo la clase exacta), asi que sin esta extension el
    esquema quedaba SIN ``securityScheme`` y emitia un warning por cada vista.
    Reutiliza el ``SessionScheme`` built-in (produce ``cookieAuth``).
    """
    target_class = 'addons.users.authentication.CsrfExemptSessionAuthentication'
    name = 'cookieAuth'


class PYTokenObtainPairSerializerExtension(OpenApiSerializerExtension):
    """
    Extiende la documentación de PYTokenObtainPairSerializer.

    El serializer de login de PracticaYoruba añade un campo 'user' a
    la respuesta de simplejwt. Sin esta extensión, Swagger muestra
    "No response body" porque la introspección automática falla en
    el override del método validate().

    Respuesta real del endpoint POST /api/v1/auth/login/:
        {
            "access":  "<jwt_access_token>",
            "refresh": "<jwt_refresh_token>",
            "user": {
                "id": 1,
                "username": "...",
                "email": "...",
                "first_name": "...",
                "last_name": "...",
                "is_staff": false,
                "avatar_url": null
            }
        }
    """
    target_class = 'addons.users.tokens.PYTokenObtainPairSerializer'

    def map_serializer(self, auto_schema, direction):
        if direction == 'request':
            fixed = inline_serializer('LoginRequest', fields={
                'username': serializers.CharField(
                    help_text='Nombre de usuario (se normaliza a minúsculas).'
                ),
                'password': serializers.CharField(write_only=True),
            })
        else:
            fixed = inline_serializer('LoginResponse', fields={
                'access':  serializers.CharField(
                    read_only=True,
                    help_text='JWT access token. Validez: 15 minutos.'
                ),
                'refresh': serializers.CharField(
                    read_only=True,
                    help_text='JWT refresh token. Validez: 1 día.'
                ),
                'user': inline_serializer('LoginUser', fields={
                    'id':         serializers.IntegerField(read_only=True),
                    'username':   serializers.CharField(read_only=True),
                    'email':      serializers.EmailField(read_only=True),
                    'first_name': serializers.CharField(read_only=True),
                    'last_name':  serializers.CharField(read_only=True),
                    'is_staff':   serializers.BooleanField(read_only=True),
                    'avatar_url': serializers.CharField(
                        read_only=True, allow_null=True
                    ),
                }),
            })
        return auto_schema._map_serializer(fixed, direction)




class TokenBlacklistViewFix(OpenApiViewExtension):
    """
    Documenta POST /api/v1/auth/logout/ (TokenBlacklistView de simplejwt).

    simplejwt usa TokenBlacklistSerializer como input y retorna HTTP 200
    con body vacío. drf-spectacular no puede introspectarlo porque
    la view no declara serializer_class explícito en la respuesta.

    Body:  {"refresh": "<refresh_token>"}
    Resp:  HTTP 200 vacío (el refresh token queda en blacklist)
    """
    target_class = 'rest_framework_simplejwt.views.TokenBlacklistView'

    def view_replacement(self):
        LogoutRequest = inline_serializer('LogoutRequest', fields={
            'refresh': serializers.CharField(
                help_text='Refresh token a invalidar (se añade a blacklist).'
            ),
        })

        @extend_schema(
            summary='Cerrar sesión',
            description=(
                'Invalida el refresh token en la blacklist de simplejwt. '
                'Tras el logout el access token sigue válido hasta que expire '
                '(máximo 15 minutos). El refresh token queda inutilizable.'
            ),
            request=LogoutRequest,
            responses={
                200: OpenApiResponse(description='Sesión cerrada. Token invalidado.'),
                400: OpenApiResponse(description='Token inválido o ya en blacklist.'),
                401: OpenApiResponse(description='No autenticado.'),
            },
            tags=['auth'],
        )
        class Fixed(self.target_class):
            pass

        return Fixed
