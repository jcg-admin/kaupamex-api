"""
Views — apps.questions (P-11 / UC-QST-01..04).

Public:
  POST /api/v1/products/<product_id>/questions/ — UC-QST-01 ask
  GET  /api/v1/products/<product_id>/questions/ — UC-QST-01 public list (ANSWERED only)

Admin:
  GET  /api/v1/admin/questions/                           UC-QST-03 queue
  POST /api/v1/admin/questions/<question_id>/answer/      UC-QST-02
  POST /api/v1/admin/questions/<question_id>/approve/     UC-QST-04
  POST /api/v1/admin/questions/<question_id>/reject/      UC-QST-04
"""
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.catalogue.models import Product
from .models import ProductQuestion, QuestionStatus
from .serializers import (
    PublicQuestionItemSerializer,
    PublicQuestionCreateSerializer,
    AdminQuestionItemSerializer,
    AdminAnswerSerializer,
)


VALID_STATUSES = {s[0] for s in QuestionStatus.choices}


class ProductQuestionsView(APIView):
    """
    GET  /api/v1/products/<product_id>/questions/ — UC-QST-01 public list
    POST /api/v1/products/<product_id>/questions/ — UC-QST-01 ask
    """
    permission_classes = [AllowAny]

    def _get_product(self, product_id):
        # H-CICLO23-03: filtrar sólo productos activos y publicados.
        # Sin este filtro, cualquiera podría listar preguntas de productos
        # inactivos o enviar preguntas a productos que ya no existen
        # públicamente, pudiendo crear ruido en la cola de moderación.
        try:
            return Product.objects.get(pk=product_id, is_active=True, is_published=True)
        except Product.DoesNotExist:
            raise NotFound({'detail': 'Producto no encontrado.',
                            'codigo_error': 'PRODUCT_NOT_FOUND'})

    @extend_schema(
        summary='Listar preguntas públicas del producto (UC-QST-01)',
        tags=['questions'],
        responses={200: PublicQuestionItemSerializer(many=True)},
    )
    def get(self, request, product_id):
        product = self._get_product(product_id)
        # Public: only ANSWERED with non-empty answer_body
        qs = (
            ProductQuestion.objects
            .filter(
                product=product,
                status=QuestionStatus.ANSWERED,
            )
            .exclude(answer_body='')
            .select_related('asker_user')
            .order_by('-created_at')
        )
        return Response({'results': PublicQuestionItemSerializer(qs, many=True).data})

    @extend_schema(
        summary='Enviar pregunta sobre el producto (UC-QST-01)',
        tags=['questions'],
        responses={201: PublicQuestionItemSerializer, 400: None},
    )
    def post(self, request, product_id):
        product = self._get_product(product_id)

        ser = PublicQuestionCreateSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        vdata = ser.validated_data

        question = ProductQuestion.objects.create(
            product=product,
            body=vdata['body'],
            asker_name=vdata.get('asker_name', ''),
            asker_email=vdata.get('asker_email', ''),
            asker_user=request.user if request.user.is_authenticated else None,
            status=QuestionStatus.PENDING,
        )
        return Response(
            PublicQuestionItemSerializer(question).data,
            status=status.HTTP_201_CREATED,
        )


class _AdminOnly:
    permission_classes = [IsAuthenticated, IsAdminUser]


class AdminQuestionsListView(_AdminOnly, APIView):
    """GET /api/v1/admin/questions/ — UC-QST-03 cola de moderación."""

    @extend_schema(
        summary='Cola de preguntas (UC-QST-03)',
        parameters=[OpenApiParameter('status', str, required=False)],
        tags=['questions'],
        responses={200: AdminQuestionItemSerializer(many=True)},
    )
    def get(self, request):
        status_filter = request.query_params.get('status')

        if status_filter is not None:
            if status_filter not in VALID_STATUSES:
                return Response(
                    {'detail': f'Estado inválido: {status_filter!r}.',
                     'codigo_error': 'INVALID_STATUS',
                     'valid_statuses': list(VALID_STATUSES)},
                    status=400,
                )
            qs = ProductQuestion.objects.filter(status=status_filter)
        else:
            qs = ProductQuestion.objects.all()

        qs = qs.select_related('product').order_by('created_at')
        return Response({'results': AdminQuestionItemSerializer(qs, many=True).data})


class AdminQuestionAnswerView(_AdminOnly, APIView):
    """POST /api/v1/admin/questions/<question_id>/answer/ — UC-QST-02 responder."""

    @extend_schema(
        summary='Responder pregunta (UC-QST-02)',
        tags=['questions'],
        responses={200: AdminQuestionItemSerializer, 400: None, 404: None},
    )
    def post(self, request, question_id):
        try:
            question = ProductQuestion.objects.get(pk=question_id)
        except ProductQuestion.DoesNotExist:
            raise NotFound({'detail': 'Pregunta no encontrada.',
                            'codigo_error': 'QUESTION_NOT_FOUND'})

        # H-CICLO23-02: prevenir sobre-escritura de respuesta ya publicada.
        # Una pregunta en estado ANSWERED ya tiene respuesta visible para el
        # comprador; permitir re-responder sin restricción puede reemplazar
        # contenido aprobado por un error de moderador. Si es necesario
        # corregir la respuesta, primero se rechaza la pregunta y luego se
        # vuelve a responder.
        if question.status == QuestionStatus.ANSWERED and question.answer_body:
            return Response(
                {'detail': 'La pregunta ya tiene una respuesta publicada.',
                 'codigo_error': 'QUESTION_ALREADY_ANSWERED'},
                status=status.HTTP_409_CONFLICT,
            )

        ser = AdminAnswerSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        answer_body = ser.validated_data['answer_body']

        question.answer_body = answer_body
        question.status = QuestionStatus.ANSWERED
        question.answered_at = timezone.now()
        question.answered_by = request.user
        question.save(update_fields=['answer_body', 'status', 'answered_at', 'answered_by', 'updated_at'])
        return Response(AdminQuestionItemSerializer(question).data)


class AdminQuestionApproveView(_AdminOnly, APIView):
    """POST /api/v1/admin/questions/<question_id>/approve/ — UC-QST-04."""

    @extend_schema(
        summary='Aprobar pregunta (UC-QST-04)',
        tags=['questions'],
        responses={200: AdminQuestionItemSerializer, 409: None, 404: None},
    )
    def post(self, request, question_id):
        try:
            question = ProductQuestion.objects.get(pk=question_id)
        except ProductQuestion.DoesNotExist:
            raise NotFound({'detail': 'Pregunta no encontrada.',
                            'codigo_error': 'QUESTION_NOT_FOUND'})

        # Cannot approve without an answer
        if not question.answer_body:
            return Response(
                {'detail': 'No se puede aprobar sin respuesta.',
                 'codigo_error': 'NO_ANSWER_BODY'},
                status=status.HTTP_409_CONFLICT,
            )

        question.status = QuestionStatus.ANSWERED
        question.save(update_fields=['status', 'updated_at'])
        return Response(AdminQuestionItemSerializer(question).data)


class AdminQuestionRejectView(_AdminOnly, APIView):
    """POST /api/v1/admin/questions/<question_id>/reject/ — UC-QST-04."""

    @extend_schema(
        summary='Rechazar pregunta (UC-QST-04)',
        tags=['questions'],
        responses={200: AdminQuestionItemSerializer, 404: None},
    )
    def post(self, request, question_id):
        try:
            question = ProductQuestion.objects.get(pk=question_id)
        except ProductQuestion.DoesNotExist:
            raise NotFound({'detail': 'Pregunta no encontrada.',
                            'codigo_error': 'QUESTION_NOT_FOUND'})
        question.status = QuestionStatus.REJECTED
        question.save(update_fields=['status', 'updated_at'])
        return Response(AdminQuestionItemSerializer(question).data)
