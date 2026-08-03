"""``SubscriberListItemSerializer`` — item del listado admin (UC-NEW-03).

``Serializer`` plano (no ``ModelSerializer``): la vista arma el cuerpo desde
``services.serialize_item`` y esto define sólo el schema OpenAPI.
"""
from rest_framework import serializers


class SubscriberListItemSerializer(serializers.Serializer):
    """UC-NEW-03 — admin list item (schema del contrato de respuesta)."""

    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    status = serializers.CharField(read_only=True)
    confirmed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    unsubscribed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
