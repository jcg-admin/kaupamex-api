"""Serializers — apps.platform.authz.

Superficie pública para el cliente admin: las capacidades del usuario
autenticado y el árbol de menú podado por esas capacidades (DEC-08/09).
"""
from rest_framework import serializers

from apps.platform.authz.models import MenuItem


class MenuItemNodeSerializer(serializers.ModelSerializer):
    """Nodo del árbol de menú. ``children`` se rellena en la vista (ya podado)."""

    capability = serializers.CharField(
        source='required_capability.code', default=None, read_only=True,
    )
    children = serializers.SerializerMethodField()

    class Meta:
        model = MenuItem
        fields = ['key', 'label', 'route', 'icon', 'order', 'capability', 'children']

    def get_children(self, obj):
        # ``obj._visible_children`` lo fija la vista con el subárbol ya filtrado.
        kids = getattr(obj, '_visible_children', [])
        return MenuItemNodeSerializer(kids, many=True).data
