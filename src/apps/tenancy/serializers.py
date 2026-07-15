"""Serializers — apps.tenancy (consola L0 del operador Kaupamex).

Solo lectura del directorio de tenants (UC-PLT-12). El detalle expone el estado
del tenant + resumen de módulos activos y conteo de usuarios, sin datos
sensibles de otros tenants (el operador L0 es cross-tenant por definición).
"""
from rest_framework import serializers

from apps.tenancy.models import Tenant


class TenantSerializer(serializers.ModelSerializer):
    """Fila/detalle de un tenant en el directorio del operador (read-only)."""

    active_modules = serializers.SerializerMethodField()
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Tenant
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
