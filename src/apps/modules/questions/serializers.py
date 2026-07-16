"""
Serializers — apps.modules.questions.

JSON keys in English (DEC-DOC-005).
"""
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from .models import ProductQuestion, QuestionStatus



class PublicQuestionItemSerializer(serializers.ModelSerializer):
    """UC-QST-02 — public listing item (approved + answered only).

    H-CICLO37-04: ProductQuestionsListPage.jsx accede a ``q.answer.body``
    (objeto anidado) pero el serializer sólo exponía el campo plano
    ``answer_body``. La condicion ``q.answer &&`` siempre era falsy →
    las respuestas de admin nunca se renderizaban. Se agrega el campo
    ``answer`` como SerializerMethodField con la estructura anidada
    que espera la UI.
    """

    asker_name = serializers.SerializerMethodField()
    answer     = serializers.SerializerMethodField()

    class Meta:
        model = ProductQuestion
        fields = [
            'id', 'product', 'asker_name', 'body', 'status',
            'answer_body', 'answered_at', 'created_at',
            'answer',
        ]
        read_only_fields = fields

    def get_asker_name(self, obj) -> str:
        # Anonimo si no se provee nombre.
        if obj.asker_user_id and not obj.asker_name:
            return obj.asker_user.email if obj.asker_user else 'Usuario'
        return obj.asker_name or 'Anonimo'

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_answer(self, obj):
        """Objeto anidado {body, answered_at} que consume la UI.
        Retorna None si la pregunta no tiene respuesta (UC-QST-02).
        """
        if not obj.answer_body:
            return None
        return {
            'body':        obj.answer_body,
            'answered_at': obj.answered_at,
        }


class PublicQuestionCreateSerializer(serializers.Serializer):
    """UC-QST-01 — public ask body."""

    body = serializers.CharField(min_length=3, max_length=5000)
    asker_name = serializers.CharField(
        required=False, allow_blank=True, max_length=120,
    )
    asker_email = serializers.EmailField(required=False, allow_blank=True)

    def validate(self, attrs):
        request = self.context.get('request')
        user = getattr(request, 'user', None) if request else None
        is_authenticated = bool(user and user.is_authenticated)
        if not is_authenticated:
            # Para anonimos exigimos nombre + email.
            if not attrs.get('asker_name'):
                raise serializers.ValidationError({
                    'asker_name': 'Requerido para usuarios anonimos.',
                })
            if not attrs.get('asker_email'):
                raise serializers.ValidationError({
                    'asker_email': 'Requerido para usuarios anonimos.',
                })
        return attrs


class AdminQuestionItemSerializer(serializers.ModelSerializer):
    """UC-QST-03 — admin queue item.

    H-CICLO36-04: product era un PK entero (FK sin nested serializer).
    La UI accedía q.product.name → undefined. Se expone product_name
    como campo plano adicional para el panel admin.
    """

    product_name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        model = ProductQuestion
        fields = [
            'id', 'product', 'product_name', 'asker_user', 'asker_name', 'asker_email',
            'body', 'status',
            'answer_body', 'answered_at', 'answered_by',
            'created_at',
        ]
        read_only_fields = fields


class AdminAnswerSerializer(serializers.Serializer):
    """UC-QST-04 — admin answer body."""

    answer_body = serializers.CharField(min_length=3, max_length=5000)


# Aliases for view compatibility
ProductQuestionSerializer      = PublicQuestionItemSerializer
ProductQuestionAdminSerializer = AdminQuestionItemSerializer
