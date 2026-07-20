"""Serializers — addons.reports (D-19 async export)."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from addons.base.models import ExportJob


class ExportJobSerializer(serializers.ModelSerializer):
    """Status payload for an async export job.

    ``download_url`` is only populated when the job is DONE: it is a signed,
    time-limited link (~1h) handled by the status view, which injects the
    absolute URL into the serializer context under ``download_url``.
    """

    job_id = serializers.IntegerField(source='id', read_only=True)
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = ExportJob
        fields = [
            'job_id', 'status', 'params', 'error_detail',
            'download_url', 'created_at', 'updated_at', 'expires_at',
        ]
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.STR)
    def get_download_url(self, obj):
        return self.context.get('download_url') or None
