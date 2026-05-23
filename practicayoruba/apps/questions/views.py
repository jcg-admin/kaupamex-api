"""
Views — apps.questions (P-11 / UC-QST-01..04).

Public:
  GET  /api/v1/products/<product_id>/questions/ — UC-QST-01

Admin:
  GET  /api/v1/admin/questions/                  UC-QST-03 queue
  POST /api/v1/admin/questions/<id>/answer/      UC-QST-02
  POST /api/v1/admin/questions/<id>/approve/     UC-QST-04
  POST /api/v1/admin/questions/<id>/reject/      UC-QST-04
"""
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.catalogue.models import Product
from .models import ProductQuestion
from .serializers import ProductQuestionSerializer, ProductQuestionAdminSerializer




class ProductQuestionsView(APIView):
    """
    GET  /api/v1/products/<product_id>/questions/ — UC-QST-01
    POST /api/v1/products/<product_id>/questions/ — UC-QST-02
    """
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Listar preguntas aprobadas del producto (UC-QST-01)',
        tags=['questions'],
        responses={200: ProductQuestionSerializer(many=True)},
    )
    def get(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise NotFound({'detail': 'Producto no encontrado.',
                            'codigo_error': 'PRODUCT_NOT_FOUND'})
        qs = (
            ProductQuestion.objects
            .filter(product=product, status=ProductQuestion.STATUS_APPROVED)
            .order_by('-created_at')
        )
        return Response(ProductQuestionSerializer(qs, many=True).data)

    @extend_schema(
        summary='Enviar pregunta sobre el producto (UC-QST-02)',
        tags=['questions'],
        responses={201: ProductQuestionSerializer, 400: None},
    )
    def post(self, request, product_id):
        try:
            product = Product.objects.get(pk=product_id)
        except Product.DoesNotExist:
            raise NotFound({'detail': 'Producto no encontrado.',
                            'codigo_error': 'PRODUCT_NOT_FOUND'})

        question_text = (request.data.get('question') or '').strip()
        asker_name    = (request.data.get('asker_name') or '').strip()
        asker_email   = (request.data.get('asker_email') or '').strip()

        if not question_text:
            raise ValidationError({'question': 'La pregunta es requerida.'})

        question = ProductQuestion.objects.create(
            product=product,
            question=question_text,
            asker_name=asker_name,
            asker_email=asker_email,
            status=ProductQuestion.STATUS_PENDING,
        )
        return Response(
            ProductQuestionSerializer(question).data,
            status=status.HTTP_201_CREATED,
        )


class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]


class AdminQuestionsListView(_AdminOnly, APIView):
    """GET /api/v1/admin/questions/ — UC-QST-03 cola de moderación."""

    @extend_schema(
        summary='Cola de preguntas pendientes (UC-QST-03)',
        parameters=[OpenApiParameter('status', str, required=False)],
        tags=['questions'],
        responses={200: ProductQuestionAdminSerializer(many=True)},
    )
    def get(self, request):
        status_filter = request.query_params.get('status', ProductQuestion.STATUS_PENDING)
        qs = (
            ProductQuestion.objects
            .filter(status=status_filter)
            .select_related('product')
            .order_by('created_at')
        )
        return Response(ProductQuestionAdminSerializer(qs, many=True).data)


class AdminQuestionAnswerView(_AdminOnly, APIView):
    """POST /api/v1/admin/questions/<id>/answer/ — UC-QST-02 responder."""

    @extend_schema(
        summary='Responder pregunta (UC-QST-02)',
        tags=['questions'],
        responses={200: ProductQuestionAdminSerializer, 400: None, 404: None},
    )
    def post(self, request, pk):
        try:
            question = ProductQuestion.objects.get(pk=pk)
        except ProductQuestion.DoesNotExist:
            raise NotFound({'detail': 'Pregunta no encontrada.',
                            'codigo_error': 'QUESTION_NOT_FOUND'})

        answer = (request.data.get('answer') or '').strip()
        if not answer:
            raise ValidationError({'answer': 'La respuesta es requerida.'})

        question.answer = answer
        question.status = ProductQuestion.STATUS_APPROVED
        question.save(update_fields=['answer', 'status'])
        return Response(ProductQuestionAdminSerializer(question).data)


class AdminQuestionApproveView(_AdminOnly, APIView):
    """POST /api/v1/admin/questions/<id>/approve/ — UC-QST-04."""

    @extend_schema(
        summary='Aprobar pregunta (UC-QST-04)',
        tags=['questions'],
        responses={200: ProductQuestionAdminSerializer, 404: None},
    )
    def post(self, request, pk):
        try:
            question = ProductQuestion.objects.get(pk=pk)
        except ProductQuestion.DoesNotExist:
            raise NotFound({'detail': 'Pregunta no encontrada.',
                            'codigo_error': 'QUESTION_NOT_FOUND'})
        question.status = ProductQuestion.STATUS_APPROVED
        question.save(update_fields=['status'])
        return Response(ProductQuestionAdminSerializer(question).data)


class AdminQuestionRejectView(_AdminOnly, APIView):
    """POST /api/v1/admin/questions/<id>/reject/ — UC-QST-04."""

    @extend_schema(
        summary='Rechazar pregunta (UC-QST-04)',
        tags=['questions'],
        responses={200: ProductQuestionAdminSerializer, 404: None},
    )
    def post(self, request, pk):
        try:
            question = ProductQuestion.objects.get(pk=pk)
        except ProductQuestion.DoesNotExist:
            raise NotFound({'detail': 'Pregunta no encontrada.',
                            'codigo_error': 'QUESTION_NOT_FOUND'})
        question.status = ProductQuestion.STATUS_REJECTED
        question.save(update_fields=['status'])
        return Response(ProductQuestionAdminSerializer(question).data)
