"""Serializers — addons.auto_backup (UC-ADM-05)."""
from rest_framework import serializers
from .models import BackupRecord


class BackupRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = BackupRecord
        fields = [
            'id', 'type', 'status', 'filename',
            'size_bytes', 'download_url', 'error_detail',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields
