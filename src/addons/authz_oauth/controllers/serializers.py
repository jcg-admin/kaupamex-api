"""Serializers — addons.authz_oauth."""
from urllib.parse import urlencode

from rest_framework import serializers

from addons.authz_oauth.models import OauthProvider


class OauthProviderSerializer(serializers.ModelSerializer):
    """CRUD admin del proveedor (capability-gated)."""

    class Meta:
        model = OauthProvider
        fields = [
            'id', 'name', 'client_id', 'auth_endpoint', 'scope',
            'validation_endpoint', 'data_endpoint', 'enabled', 'css_class',
            'body', 'sequence', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OauthProviderPublicSerializer(serializers.ModelSerializer):
    """Lo que ve la página de login del SPA — ≙ ``list_providers`` del
    controlador de la referencia (main.py:29-46): sólo habilitados, con el
    ``auth_link`` armado (response_type=token + client_id + redirect_uri +
    scope + state que el SPA completa)."""

    auth_link = serializers.SerializerMethodField()

    class Meta:
        model = OauthProvider
        fields = ['id', 'name', 'auth_endpoint', 'scope', 'css_class',
                  'body', 'auth_link']

    def get_auth_link(self, obj) -> str:
        redirect_uri = self.context.get('redirect_uri', '')
        params = {
            'response_type': 'token',
            'client_id': obj.client_id,
            'redirect_uri': redirect_uri,
            'scope': obj.scope,
        }
        return '%s?%s' % (obj.auth_endpoint, urlencode(params))


class OauthSigninSerializer(serializers.Serializer):
    """Payload del signin: el fragmento OAuth que el SPA recibió del
    proveedor (≙ los ``kw`` de ``/auth_oauth/signin``)."""

    provider = serializers.IntegerField()
    access_token = serializers.CharField()
    state = serializers.CharField(required=False, allow_blank=True)
