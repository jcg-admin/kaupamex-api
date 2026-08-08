"""``SubscribeSerializer`` — request body de la suscripción (UC-NEW-01)."""
from rest_framework import serializers


class SubscribeSerializer(serializers.Serializer):
    """UC-NEW-01 — request body. JSON keys en inglés (DEC-DOC-005)."""

    email = serializers.EmailField()
