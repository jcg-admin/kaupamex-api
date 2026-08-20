"""Serializers — ``addons.auto_backup`` (UC-ADM-05)."""
from rest_framework import serializers

from addons.auto_backup.models import DbBackupDetails


class DbBackupDetailsSerializer(serializers.ModelSerializer):
    """Una corrida de respaldo tal como la lista el operador L0.

    ``file_path`` NO se expone: es una ruta absoluta del servidor y el
    cliente no la necesita — para descargar está ``url``, que es lo que la
    fuente escribe en el campo homónimo.
    """

    class Meta:
        model = DbBackupDetails
        fields = [
            'id', 'name', 'url', 'db_backup_id',
            'type', 'status', 'size_bytes', 'error_detail',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields
