"""``UnsubscribeSerializer`` — baja pública por token firmado (UC-NEW-02)."""
from rest_framework import serializers


class UnsubscribeSerializer(serializers.Serializer):
    """UC-NEW-02 — public unsubscribe by signed token."""

    token = serializers.CharField(min_length=8, max_length=200)
