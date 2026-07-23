from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import StaticContent, StaticContentVersion



class StaticContentVersionSerializer(serializers.ModelSerializer):
    changed_by_username = serializers.SerializerMethodField()

    class Meta:
        model  = StaticContentVersion
        fields = [
            'id', 'version', 'title', 'body',
            'changed_by', 'changed_by_username', 'created_at',
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_changed_by_username(self, obj):
        return obj.changed_by.email if obj.changed_by_id else None


class StaticContentSerializer(serializers.ModelSerializer):
    versions = StaticContentVersionSerializer(many=True, read_only=True)

    class Meta:
        model  = StaticContent
        fields = ['id', 'slug', 'title', 'body', 'version',
                  'updated_at', 'versions']
        read_only_fields = ['version', 'updated_at']
