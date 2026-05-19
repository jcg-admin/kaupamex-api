"""
Serializers — apps.contact.

JSON keys in English (DEC-DOC-005).
"""
from rest_framework import serializers

from .models import ContactMessage


class ContactMessageCreateSerializer(serializers.ModelSerializer):
    """UC-COM-01 — public submission body."""

    class Meta:
        model = ContactMessage
        fields = ['name', 'email', 'phone', 'subject', 'body']
        extra_kwargs = {
            'name': {'min_length': 2, 'max_length': 120},
            'subject': {'min_length': 3, 'max_length': 200},
            'body': {'min_length': 3},
            'phone': {'required': False, 'allow_blank': True},
        }


class ContactMessageListItemSerializer(serializers.ModelSerializer):
    """UC-COM-02 — admin inbox list/detail item."""

    class Meta:
        model = ContactMessage
        fields = [
            'id', 'name', 'email', 'phone', 'subject', 'body',
            'read', 'replied', 'created_at',
            'reply_body', 'reply_sent_at',
        ]
        read_only_fields = fields


class ContactMessageReplySerializer(serializers.Serializer):
    """UC-COM-03 — admin reply body."""

    reply_body = serializers.CharField(min_length=3)
