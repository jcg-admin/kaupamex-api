"""Serializers — apps.reviews (P-14)."""
from rest_framework import serializers
from .models import Review



class ReviewPublicSerializer(serializers.ModelSerializer):
    """Public listing — only APPROVED reviews exposed."""
    user_display = serializers.SerializerMethodField()

    class Meta:
        model  = Review
        fields = [
            'id', 'rating', 'title', 'body',
            'user_display', 'created_at', 'helpful_count',
        ]

    def get_user_display(self, obj):
        full = obj.user.get_full_name() if obj.user_id else ''
        return full or (obj.user.username if obj.user_id else 'Anonimo')


class ReviewAdminSerializer(serializers.ModelSerializer):
    user_username    = serializers.CharField(source='user.username', read_only=True)
    product_id       = serializers.IntegerField(source='product.id', read_only=True)
    product_name     = serializers.CharField(source='product.name', read_only=True)
    order_number     = serializers.CharField(source='order.order_number', read_only=True)

    class Meta:
        model  = Review
        fields = [
            'id', 'rating', 'title', 'body', 'status', 'reject_reason',
            'user_username', 'product_id', 'product_name', 'order_number',
            'created_at', 'moderated_at',
        ]


class ReviewCreateSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    rating   = serializers.IntegerField(min_value=1, max_value=5)
    title    = serializers.CharField(max_length=120)
    body     = serializers.CharField(max_length=2000)
