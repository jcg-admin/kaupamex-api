"""
Serializers — apps.addons.notifications.

JSON keys in English (DEC-DOC-005).
"""
from rest_framework import serializers
from .models import ManualNotification, Notification, NotificationPreference, NotificationType



class NotificationSerializer(serializers.ModelSerializer):
    """UC-NOT-01..05 — item del buzon.

    H-CICLO37-01: el modelo usa el campo ``read`` pero la UI accede a
    ``is_read``. Se expone como ``is_read`` via source para alinear el
    contrato JSON con lo que consume NotificationsPage.jsx.
    """

    is_read = serializers.BooleanField(source='read', read_only=True)

    class Meta:
        model = Notification
        fields = ['id', 'type', 'subject', 'body', 'is_read', 'created_at']
        read_only_fields = fields


class NotificationPreferenceItemSerializer(serializers.Serializer):
    """UC-NOT-06 — fila del listado de preferencias."""

    type = serializers.CharField()
    enabled = serializers.BooleanField()
    mandatory = serializers.BooleanField()
    label = serializers.CharField()


class NotificationPreferenceUpdateItemSerializer(serializers.Serializer):
    """UC-NOT-06 — fila aceptada en PUT."""

    type = serializers.ChoiceField(choices=NotificationType.choices)
    enabled = serializers.BooleanField()


class NotificationPreferencesUpdateSerializer(serializers.Serializer):
    """UC-NOT-06 — request body para PUT preferences."""

    preferences = NotificationPreferenceUpdateItemSerializer(many=True)


class ManualNotificationCreateSerializer(serializers.Serializer):
    """UC-NOT-07 — request body."""

    recipient_type = serializers.ChoiceField(
        choices=ManualNotification.RecipientType.choices,
    )
    recipient_identifier = serializers.CharField(
        required=False, allow_blank=True, default='', max_length=254,
    )
    product_id = serializers.IntegerField(required=False, allow_null=True)
    subject = serializers.CharField(min_length=3, max_length=200)
    message = serializers.CharField(min_length=3, max_length=10000)

    def validate(self, attrs):
        recipient_type = attrs.get('recipient_type')
        if recipient_type == ManualNotification.RecipientType.USER:
            if not attrs.get('recipient_identifier'):
                raise serializers.ValidationError({
                    'recipient_identifier':
                        'recipient_identifier es requerido para recipient_type=USER.',
                })
        elif recipient_type == ManualNotification.RecipientType.PRODUCT_BUYERS:
            if not attrs.get('product_id'):
                raise serializers.ValidationError({
                    'product_id':
                        'product_id es requerido para recipient_type=PRODUCT_BUYERS.',
                })
        return attrs


class ManualNotificationResponseSerializer(serializers.ModelSerializer):
    """UC-NOT-07 — response body."""

    class Meta:
        model = ManualNotification
        fields = ['id', 'recipients_count', 'status']
        read_only_fields = fields
