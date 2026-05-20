"""
Views — apps.questions (UC-QST-01..04).

Public endpoints:
  POST /api/v1/products/<id>/questions/                    public ask
  GET  /api/v1/products/<id>/questions/                    public list (approved only)

Admin endpoints:
  GET  /api/v1/admin/questions/?status=...                 admin queue
  POST /api/v1/admin/questions/<id>/answer/                admin answer
  POST /api/v1/admin/questions/<id>/approve/               admin approve
  POST /api/v1/admin/questions/<id>/reject/                admin reject

JSON keys + identifiers in English (DEC-DOC-005).
"""
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalogue.models import Product

from .models import ProductQuestion, QuestionStatus
from .serializers import (
    AdminAnswerSerializer,
    AdminQuestionItemSerializer,
    PublicQuestionCreateSerializer,
    PublicQuestionItemSerializer,
)


# ── public ────────────────────────────────────────────────────────────
class ProductQuestionsView(APIView):
    """GET/POST /api/v1/products/<product_id>/questions/."""

    serializer_class = PublicQuestionItemSerializer

    def get_permissions(self):
        # GET es publico; POST requiere AllowAny (anon o autenticado).
        return [AllowAny()]

    @extend_schema(
        summary='Listar preguntas publicas de un producto',
        tags=['questions'],
        responses=PublicQuestionItemSerializer(many=True),
    )
    def get(self, request, product_id):
        get_object_or_404(Product, pk=product_id)
        qs = (
            ProductQuestion.objects
            .filter(
                product_id=product_id,
                status=QuestionStatus.ANSWERED,
            )
            .exclude(answer_body='')
        )
        data = PublicQuestionItemSerializer(qs, many=True).data
        return Response({'results': data})

    @extend_schema(
        summary='Crear pregunta de producto',
        tags=['questions'],
        request=PublicQuestionCreateSerializer,
    )
    def post(self, request, product_id):
        # 404 first: el contrato dice que un producto desconocido devuelve
        # 404 aunque el body no sea valido.
        product = get_object_or_404(Product, pk=product_id)
        serializer = PublicQuestionCreateSerializer(
            data=request.data, context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        user = request.user if request.user.is_authenticated else None
        question = ProductQuestion.objects.create(
            product=product,
            asker_user=user,
            asker_name=payload.get('asker_name', '') or '',
            asker_email=payload.get('asker_email', '') or '',
            body=payload['body'],
            status=QuestionStatus.PENDING,
        )
        return Response(
            {
                'id': question.pk,
                'product': product.pk,
                'body': question.body,
                'status': question.status,
                'created_at': question.created_at,
            },
            status=status.HTTP_201_CREATED,
        )


# ── admin ─────────────────────────────────────────────────────────────
class AdminQuestionsListView(APIView):
    """GET /api/v1/admin/questions/."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Listar preguntas para moderacion',
        tags=['questions'],
        parameters=[
            OpenApiParameter('status', str, required=False),
        ],
        responses=AdminQuestionItemSerializer(many=True),
    )
    def get(self, request):
        qs = ProductQuestion.objects.all()
        status_filter = request.query_params.get('status')
        if status_filter:
            valid = {c[0] for c in QuestionStatus.choices}
            if status_filter not in valid:
                return Response(
                    {'error_code': 'INVALID_STATUS',
                     'detail': 'status invalido.'},
                    status=400,
                )
            qs = qs.filter(status=status_filter)
        data = AdminQuestionItemSerializer(qs, many=True).data
        return Response({'results': data})


class AdminQuestionAnswerView(APIView):
    """POST /api/v1/admin/questions/<id>/answer/."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    @extend_schema(
        summary='Responder pregunta',
        tags=['questions'],
        request=AdminAnswerSerializer,
        responses=AdminQuestionItemSerializer,
    )
    def post(self, request, question_id):
        question = get_object_or_404(ProductQuestion, pk=question_id)
        serializer = AdminAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question.answer_body = serializer.validated_data['answer_body']
        question.answered_at = timezone.now()
        question.answered_by = request.user
        question.status = QuestionStatus.ANSWERED
        question.save(update_fields=[
            'answer_body', 'answered_at', 'answered_by',
            'status', 'updated_at',
        ])
        return Response(AdminQuestionItemSerializer(question).data)


class AdminQuestionApproveView(APIView):
    """POST /api/v1/admin/questions/<id>/approve/."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = AdminQuestionItemSerializer

    @extend_schema(
        summary='Aprobar pregunta respondida',
        tags=['questions'],
    )
    def post(self, request, question_id):
        question = get_object_or_404(ProductQuestion, pk=question_id)
        if not question.answer_body:
            return Response(
                {'error_code': 'NOT_ANSWERED',
                 'detail': 'La pregunta no tiene respuesta.'},
                status=409,
            )
        question.status = QuestionStatus.ANSWERED
        question.save(update_fields=['status', 'updated_at'])
        return Response({'id': question.pk, 'status': question.status})


class AdminQuestionRejectView(APIView):
    """POST /api/v1/admin/questions/<id>/reject/."""

    permission_classes = [IsAuthenticated, IsAdminUser]
    serializer_class = AdminQuestionItemSerializer

    @extend_schema(
        summary='Rechazar pregunta',
        tags=['questions'],
    )
    def post(self, request, question_id):
        question = get_object_or_404(ProductQuestion, pk=question_id)
        question.status = QuestionStatus.REJECTED
        question.save(update_fields=['status', 'updated_at'])
        return Response({'id': question.pk, 'status': question.status})
