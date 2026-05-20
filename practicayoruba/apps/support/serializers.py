"""
Serializers — apps.support.

Cumplen los contratos JSON declarados en UC-SUPP-01..05 (PARTE 7C).
"""
from rest_framework import serializers

from .models import SupportTicket, SupportTicketReply


class SupportTicketCreateSerializer(serializers.Serializer):
    """
    UC-SUPP-01 — request body.

    Valida AC-03:

    * ``order_id`` solo es aceptado si la orden existe y pertenece al
      comprador autenticado. Para no revelar la existencia de ordenes
      ajenas (RNF-SEC-003) se devuelve ``ORDER_NOT_FOUND`` aunque la
      orden exista pero pertenezca a otro usuario.
    """

    subject = serializers.CharField(min_length=5, max_length=150)
    body = serializers.CharField(min_length=10)
    category = serializers.ChoiceField(
        choices=SupportTicket.Category.choices,
        required=False,
        default=SupportTicket.Category.GENERAL,
    )
    order_id = serializers.IntegerField(required=False, allow_null=True)
    priority = serializers.ChoiceField(
        choices=SupportTicket.Priority.choices,
        required=False,
        default=SupportTicket.Priority.NORMAL,
    )

    def validate_order_id(self, value):
        if value in (None, ''):
            return value
        request = self.context.get('request')
        if request is None or not getattr(request.user, 'is_authenticated', False):
            return value  # las views protegen con IsAuthenticated
        # Import diferido para evitar ciclos en apps cargando.
        from apps.orders.models import Order
        if not Order.objects.filter(pk=value, user=request.user).exists():
            raise serializers.ValidationError({
                'error_code': 'ORDER_NOT_FOUND',
                'detail':     'La orden no existe o no pertenece al comprador.',
            })
        return value


class SupportTicketCreateResponseSerializer(serializers.ModelSerializer):
    """UC-SUPP-01 — response body."""

    ticket_id = serializers.IntegerField(source='pk', read_only=True)

    class Meta:
        model = SupportTicket
        fields = ['ticket_id', 'status', 'subject', 'created_at', 'order_id']
        read_only_fields = fields


class SupportTicketListSerializer(serializers.ModelSerializer):
    """UC-SUPP-02 — list item."""

    ticket_id = serializers.IntegerField(source='pk', read_only=True)

    class Meta:
        model = SupportTicket
        fields = [
            'ticket_id', 'subject', 'status', 'priority',
            'category', 'order_id', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class SupportTicketReplySerializer(serializers.ModelSerializer):
    """UC-SUPP-03 — reply representation."""

    reply_id = serializers.IntegerField(source='pk', read_only=True)
    ticket_id = serializers.IntegerField(read_only=True)
    sent_at = serializers.DateTimeField(source='created_at', read_only=True)
    author = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicketReply
        fields = [
            'reply_id', 'ticket_id', 'author', 'body',
            'is_internal_note', 'sent_at',
        ]
        read_only_fields = fields

    def get_author(self, obj) -> str:
        if obj.author is None:
            return 'SYSTEM'
        return 'ADMIN' if obj.author.is_staff else 'BUYER'


class SupportTicketDetailSerializer(serializers.ModelSerializer):
    """UC-SUPP-02 — detail with conversation thread."""

    ticket_id = serializers.IntegerField(source='pk', read_only=True)
    replies = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()
    buyer = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = [
            'ticket_id', 'subject', 'body', 'status', 'priority',
            'category', 'order_id', 'created_at', 'updated_at',
            'replies', 'available_actions', 'buyer',
        ]
        read_only_fields = fields

    def get_replies(self, obj) -> list:
        request = self.context.get('request')
        is_staff = bool(request and request.user.is_authenticated and request.user.is_staff)
        qs = obj.replies.all().order_by('created_at')
        if not is_staff:
            qs = qs.filter(is_internal_note=False)
        return SupportTicketReplySerializer(qs, many=True).data

    def get_available_actions(self, obj) -> list:
        if obj.status == SupportTicket.Status.CLOSED:
            return ['REOPEN']
        return ['REPLY', 'CLOSE']

    def get_buyer(self, obj) -> dict | None:
        request = self.context.get('request')
        if not (request and request.user.is_authenticated and request.user.is_staff):
            return None
        return {
            'id': obj.user_id,
            'email': obj.user.email,
            'first_name': obj.user.first_name,
        }


class SupportTicketReplyCreateSerializer(serializers.Serializer):
    """UC-SUPP-03 — reply create request."""

    body = serializers.CharField(min_length=10)
    is_internal_note = serializers.BooleanField(required=False, default=False)


class SupportTicketCloseSerializer(serializers.Serializer):
    """UC-SUPP-04 — close ticket request."""

    reason = serializers.CharField(required=False, allow_blank=True, max_length=300)
