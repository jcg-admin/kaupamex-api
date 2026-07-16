"""Serializers — apps.company (consola L0 del operador Kaupamex).

Solo lectura del directorio de companies L1 (UC-PLT-12). El detalle expone el
estado de la company + resumen de módulos activos y conteo de usuarios, sin
datos sensibles de otras companies (el operador L0 es cross-company por
definición).
"""
from rest_framework import serializers

from apps.company.models import Company


class CompanySerializer(serializers.ModelSerializer):
    """Fila/detalle de una company en el directorio del operador (read-only)."""

    active_modules = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'code', 'name', 'status',
            'billing_email', 'billing_name', 'tax_id',
            'active_modules', 'user_count', 'created_at',
        ]
        read_only_fields = fields

    def get_active_modules(self, obj):
        return sorted(obj.active_module_codes())

    def get_user_count(self, obj):
        return obj.users.count()
