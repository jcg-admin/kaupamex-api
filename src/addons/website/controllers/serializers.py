"""Serializers de páginas estáticas versionadas — ``website``.

Porte de la capa del ex-addon ``settings_app`` (retirado en ``api@115d219``
por no declarar modelos propios). ``StaticPage``/``StaticPageVersion`` ya
viven en ``website/models/static_page.py``: la referencia hospeda las
páginas del sitio en ``website`` (``website.page``), que es el destino que
el fold ya había elegido.
"""
from rest_framework import serializers

from addons.website.models import StaticPage, StaticPageVersion


class StaticPageVersionSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(
        source='created_by.email', read_only=True, default=None,
    )

    class Meta:
        model = StaticPageVersion
        fields = ['id', 'version', 'content', 'status',
                  'created_by_username', 'created_at', 'publish_at']
        read_only_fields = ['id', 'version', 'created_at']


class StaticPageSerializer(serializers.ModelSerializer):
    current_version = StaticPageVersionSerializer(read_only=True)
    slug_display = serializers.CharField(source='get_slug_display', read_only=True)

    class Meta:
        model = StaticPage
        fields = ['id', 'slug', 'slug_display', 'title', 'current_version', 'updated_at']
        read_only_fields = ['id', 'updated_at']


class StaticPagePublishSerializer(serializers.Serializer):
    """Cuerpo de la publicación: contenido + programación opcional."""

    content = serializers.CharField()
    publish_at = serializers.DateTimeField(required=False, allow_null=True)


class StaticPageRestorationSerializer(serializers.Serializer):
    """Cuerpo de la restauración v2: la versión viaja en el body, no en la ruta."""

    version = serializers.IntegerField()


class PublicStaticPageSerializer(serializers.ModelSerializer):
    """Proyección pública read-only: sólo el contenido de la versión PUBLISHED."""

    content = serializers.SerializerMethodField()
    slug_display = serializers.CharField(source='get_slug_display', read_only=True)

    class Meta:
        model = StaticPage
        fields = ['slug', 'slug_display', 'title', 'content', 'updated_at']
        read_only_fields = fields

    def get_content(self, obj) -> str:
        version = obj.current_version
        return version.content if version else ''
