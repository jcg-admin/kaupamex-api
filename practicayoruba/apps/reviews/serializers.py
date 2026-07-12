"""Serializers — apps.reviews (P-14)."""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import Review, ReviewImage



class ReviewImageSerializer(serializers.ModelSerializer):
    """UC-REV-02 cap6 — imagen adjunta a una reseña."""

    class Meta:
        model            = ReviewImage
        fields           = ['id', 'image', 'created_at']
        read_only_fields = ['id', 'created_at']


class ReviewPublicSerializer(serializers.ModelSerializer):
    """Public listing — only APPROVED reviews exposed."""
    user_display = serializers.SerializerMethodField()
    images       = ReviewImageSerializer(many=True, read_only=True)

    class Meta:
        model  = Review
        fields = [
            'id', 'rating', 'title', 'body',
            'user_display', 'created_at', 'helpful_count', 'images',
        ]

    @extend_schema_field(OpenApiTypes.STR)
    def get_user_display(self, obj):
        full = obj.user.get_full_name() if obj.user_id else ''
        return full or (obj.user.email if obj.user_id else 'Anonimo')


class ReviewAdminSerializer(serializers.ModelSerializer):
    user_username    = serializers.CharField(source='user.email', read_only=True)
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


class ReviewUpdateSerializer(serializers.Serializer):
    """UC-REV-01 Alt B — buyer edits their own pending review."""
    rating = serializers.IntegerField(min_value=1, max_value=5, required=False)
    title  = serializers.CharField(max_length=120, required=False)
    body   = serializers.CharField(max_length=2000, min_length=10, required=False)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save(update_fields=list(validated_data.keys()) + ['updated_at'])
        return instance
