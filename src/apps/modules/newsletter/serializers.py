"""
Serializers — apps.modules.newsletter.

JSON keys in English (DEC-DOC-005).
"""
from rest_framework import serializers
from .models import NewsletterCampaign, NewsletterSubscriber, SubscriberStatus



class SubscribeSerializer(serializers.Serializer):
    """UC-NEW-01 — request body."""

    email = serializers.EmailField()


class UnsubscribeSerializer(serializers.Serializer):
    """UC-NEW-02 — public unsubscribe by signed token."""

    token = serializers.CharField(min_length=8, max_length=200)


class SubscriberListItemSerializer(serializers.ModelSerializer):
    """UC-NEW-03 — admin list item."""

    class Meta:
        model = NewsletterSubscriber
        fields = [
            'id', 'email', 'status',
            'confirmed_at', 'unsubscribed_at', 'created_at',
        ]
        read_only_fields = fields


class CampaignCreateSerializer(serializers.Serializer):
    """UC-NEW-04 — admin create/send campaign."""

    subject = serializers.CharField(min_length=3, max_length=200)
    body = serializers.CharField(min_length=3, max_length=50000)
    audience_filter = serializers.ChoiceField(
        choices=SubscriberStatus.choices,
        default=SubscriberStatus.CONFIRMED,
        required=False,
    )


class CampaignResponseSerializer(serializers.ModelSerializer):
    """UC-NEW-04 — admin create response."""

    class Meta:
        model = NewsletterCampaign
        fields = [
            'id', 'subject', 'audience_filter',
            'recipients_count', 'sent_at',
        ]
        read_only_fields = fields


# Alias for view compatibility
NewsletterSubscribeSerializer = SubscribeSerializer
NewsletterSubscriberAdminSerializer = SubscriberListItemSerializer
NewsletterCampaignSerializer = CampaignResponseSerializer
