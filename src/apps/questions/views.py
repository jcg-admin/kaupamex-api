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
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from apps.authz.permissions import HasCapability
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from apps.catalogue.models import Product
from config.schema import error_response
from .models import ProductQuestion, QuestionModerationLog, QuestionStatus
from .serializers import (
    PublicQuestionItemSerializer,
    PublicQuestionCreateSerializer,
    AdminQuestionItemSerializer,
    AdminAnswerSerializer,
)


VALID_STATUSES = {s[0] for s in QuestionStatus.choices}


class AdminQuestionPagination(PageNumberPagination):
    """H-CICLO84-02: paginar cola de preguntas admin para evitar OOM."""
    page_size             = 50
    page_size_query_param = 'page_size'
    max_page_size         = 200


class PublicQuestionPagination(PageNumberPagination):
    """H-CICLO120-01: paginar listado publico de preguntas.
    Sin paginacion un producto con muchas Q&A respondidas retorna toda
    la tabla en un solo response, causando OOM en el worker y freeze
    en el cliente. page_size conservador (20) apropiado para el frontend.
    """
    page_size             = 20
    page_size_query_param = 'page_size'
    max_page_size         = 100


class ProductQuestionsView(APIView):
    """
    GET  /api/v1/products/<product_id>/questions/ — UC-QST-01 public list
    POST /api/v1/products/<product_id>/questions/ — UC-QST-01 ask
    """
    permission_classes = [AllowAny]
    # H-CICLO42-04: throttle para el POST de preguntas publicas. Sin limite
    # cualquier visitante puede inundar la cola de moderacion del admin.
    # El GET no tiene throttle_scope pero hereda AnonRateThrottle del
    # DEFAULT_THROTTLE_CLASSES global (anon: 100/hour).
    throttle_classes = [ScopedRateThrottle]
    throttle_scope   = 'question_ask'

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
        # H-CICLO120-01: paginar listado publico. Sin paginacion un producto
        # con cientos de Q&A retorna toda la tabla en un solo response,
        # causando OOM en el worker y freeze en el UI del comprador.
        paginator = PublicQuestionPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(
                PublicQuestionItemSerializer(page, many=True).data
            )
        return Response({'results': PublicQuestionItemSerializer(qs, many=True).data})

    @extend_schema(
        summary='Enviar pregunta sobre el producto (UC-QST-01)',
        tags=['questions'],
        request=PublicQuestionCreateSerializer,
        responses={201: PublicQuestionItemSerializer,
                   400: error_response('Datos inválidos'),
                   404: error_response('Producto no encontrado')},
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
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'questions.manage'


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

        # H-CICLO48-03: AdminQuestionItemSerializer accede a product.name,
        # asker_user (username) y answered_by. Sin select_related se generan
        # N+1 queries por cada pregunta en la cola. Se agregan las tres FKs.
        qs = qs.select_related('product', 'asker_user', 'answered_by').order_by('created_at')
        # H-CICLO84-02: paginar la cola de admin. Sin paginacion una tienda
        # con cientos de preguntas acumuladas retorna toda la tabla en una
        # sola respuesta, agotando memoria del worker y ancho de banda.
        paginator = AdminQuestionPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(
                AdminQuestionItemSerializer(page, many=True).data
            )
        return Response({'results': AdminQuestionItemSerializer(qs, many=True).data})


class AdminQuestionAnswerView(_AdminOnly, APIView):
    """POST /api/v1/admin/questions/<question_id>/answer/ — UC-QST-02 responder."""

    @extend_schema(
        summary='[DEPRECATED → POST /api/v2/admin/questions/<id>/answers/] Responder pregunta (UC-QST-02)',
        deprecated=True,
        tags=['questions'],
        request=AdminAnswerSerializer,
        responses={200: AdminQuestionItemSerializer,
                   400: error_response('Datos inválidos'),
                   404: error_response('Pregunta no encontrada'),
                   409: error_response('La pregunta ya tiene respuesta publicada')},
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
        summary='[DEPRECATED → PATCH /api/v2/admin/questions/<id>/status/] Aprobar pregunta (UC-QST-04)',
        deprecated=True,
        tags=['questions'],
        request=None,
        responses={200: AdminQuestionItemSerializer,
                   404: error_response('Pregunta no encontrada'),
                   409: error_response('No se puede aprobar sin respuesta')},
    )
    def post(self, request, question_id):
        try:
            question = ProductQuestion.objects.get(pk=question_id)
        except ProductQuestion.DoesNotExist:
            raise NotFound({'detail': 'Pregunta no encontrada.',
                            'codigo_error': 'QUESTION_NOT_FOUND'})

        # UC-QST-04: el admin puede editar/traducir la respuesta antes de
        # aprobar (``edited_body``). Si llega, reemplaza ``answer_body``.
        edited_body = (request.data.get('edited_body') or '').strip()
        update_fields = ['status', 'updated_at']
        if edited_body:
            question.answer_body = edited_body
            question.answered_at = timezone.now()
            if request.user.is_authenticated:
                question.answered_by = request.user
            update_fields += ['answer_body', 'answered_at', 'answered_by']

        # Cannot approve without an answer
        if not question.answer_body:
            return Response(
                {'detail': 'No se puede aprobar sin respuesta.',
                 'codigo_error': 'NO_ANSWER_BODY'},
                status=status.HTTP_409_CONFLICT,
            )

        question.status = QuestionStatus.ANSWERED
        question.save(update_fields=update_fields)
        QuestionModerationLog.objects.create(
            question=question,
            action=QuestionModerationLog.APPROVE,
            moderated_by=request.user if request.user.is_authenticated else None,
        )
        return Response(AdminQuestionItemSerializer(question).data)


class AdminQuestionRejectView(_AdminOnly, APIView):
    """POST /api/v1/admin/questions/<question_id>/reject/ — UC-QST-04."""

    @extend_schema(
        summary='[DEPRECATED → PATCH /api/v2/admin/questions/<id>/status/] Rechazar pregunta (UC-QST-04)',
        deprecated=True,
        tags=['questions'],
        request=None,
        responses={200: AdminQuestionItemSerializer,
                   404: error_response('Pregunta no encontrada')},
    )
    def post(self, request, question_id):
        try:
            question = ProductQuestion.objects.get(pk=question_id)
        except ProductQuestion.DoesNotExist:
            raise NotFound({'detail': 'Pregunta no encontrada.',
                            'codigo_error': 'QUESTION_NOT_FOUND'})

        # UC-QST-04: el motivo es requerido al rechazar y queda en auditoria.
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            return Response(
                {'detail': 'El motivo de rechazo es requerido.',
                 'codigo_error': 'MISSING_REASON'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        question.status = QuestionStatus.REJECTED
        question.save(update_fields=['status', 'updated_at'])
        QuestionModerationLog.objects.create(
            question=question,
            action=QuestionModerationLog.REJECT,
            reason=reason,
            moderated_by=request.user if request.user.is_authenticated else None,
        )
        return Response(AdminQuestionItemSerializer(question).data)


class QuestionStatusV2View(APIView):
    """PATCH /api/v2/admin/questions/<id>/status/ — Tier B."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'questions.manage'

    def patch(self, request, question_id):
        action = (request.data.get('action') or '').strip()
        if not action:
            # Back-compat: la UI envia payload status-based
            # (``{status: 'APPROVED'|'REJECTED'}``), no ``action``.
            status_val = (request.data.get('status') or '').strip().upper()
            action = {'APPROVED': 'approve',
                      'REJECTED': 'reject'}.get(status_val, '')
        if action == 'approve':
            return AdminQuestionApproveView().post(request, question_id)
        if action == 'reject':
            return AdminQuestionRejectView().post(request, question_id)
        return Response(
            {
                'detail': "action debe ser 'approve' o 'reject'.",
                'codigo_error': 'INVALID_ACTION',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
