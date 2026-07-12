"""Serializers admin — apps.authz.

Superficie del panel admin (capacidad ``permissions.manage``): el catálogo de
roles disponibles para el selector de ``/admin/permissions`` (UC-ADM-02).
Complementa ``apps.authz.serializers`` (superficie del usuario autenticado).
"""
from rest_framework import serializers

from apps.authz.models import Role


class AdminRoleSerializer(serializers.ModelSerializer):
    """Un rol del catálogo: ``id`` (para el POST de asignación), ``code``,
    ``name`` y la lista de ``capabilities`` (codes) que agrupa."""

    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ['id', 'code', 'name', 'capabilities']

    def get_capabilities(self, obj) -> list:
        # ``obj.capabilities`` viene prefetch-eado por la vista; se ordena por
        # code para un contrato estable (mismo criterio que me/capabilities).
        return sorted(c.code for c in obj.capabilities.all())
