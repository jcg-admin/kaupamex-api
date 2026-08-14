"""Serializers de campaña (UC-NEW-04) — request y schema de respuesta."""
from rest_framework import serializers

# Estados de negocio del suscriptor (ex-``newsletter.SubscriberStatus``).
NEWSLETTER_STATUS_CHOICES = [
    ('PENDING', 'Pendiente'),
    ('CONFIRMED', 'Confirmado'),
    ('UNSUBSCRIBED', 'Dado de baja'),
]


class CampaignCreateSerializer(serializers.Serializer):
    """UC-NEW-04 — admin create/send campaign."""

    subject = serializers.CharField(min_length=3, max_length=200)
    body = serializers.CharField(min_length=3, max_length=50000)
    audience_filter = serializers.ChoiceField(
        choices=NEWSLETTER_STATUS_CHOICES,
        default='CONFIRMED',
        required=False,
    )


class CampaignResponseSerializer(serializers.Serializer):
    """UC-NEW-04 — admin create response (schema del contrato)."""

    id = serializers.IntegerField(read_only=True)
    subject = serializers.CharField(read_only=True)
    audience_filter = serializers.CharField(read_only=True)
    recipients_count = serializers.IntegerField(read_only=True)
    sent_at = serializers.DateTimeField(read_only=True, allow_null=True)
