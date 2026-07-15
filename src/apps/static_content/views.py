"""
Views — apps.static_content (UC-CFG-04).

  GET   /api/v1/admin/static-content/             list
  POST  /api/v1/admin/static-content/             create page (idempotent on slug)
  GET   /api/v1/admin/static-content/<slug>/      page + version history
  PATCH /api/v1/admin/static-content/<slug>/      edit (bumps version, audit log)
"""
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated

from apps.authz.permissions import HasCapability
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import StaticContent, StaticContentVersion
from .serializers import StaticContentSerializer



class _AdminOnly:
    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'content.edit'
    serializer_class = StaticContentSerializer


_BODY_MAX_LENGTH = 102_400   # 100 KB — H-CICLO31-02: limitar contenido de página estática.


class StaticContentListView(_AdminOnly, APIView):
    @extend_schema(summary='List static content pages.',
                   tags=['static-content'],
                   operation_id='admin_static_content_list',
                   responses={200: StaticContentSerializer(many=True)})
    def get(self, request):
        qs = StaticContent.objects.all().prefetch_related('versions')
        return Response(StaticContentSerializer(qs, many=True).data)

    @extend_schema(summary='Create static content page.', tags=['static-content'],
                   responses={201: StaticContentSerializer})
    @transaction.atomic
    def post(self, request):
        slug = (request.data.get('slug') or '').strip()
        title = (request.data.get('title') or '').strip()
        body = request.data.get('body') or ''
        if not slug or not title:
            raise ValidationError({
                'detail': 'slug y title son requeridos.',
                'codigo_error': 'REQUIRED_FIELDS_MISSING',
            })
        # H-CICLO31-02: sin límite, un admin podría publicar una página con
        # decenas de MB de contenido, saturando la BD y la respuesta HTTP.
        if len(body) > _BODY_MAX_LENGTH:
            raise ValidationError({
                'detail': f'body no puede superar {_BODY_MAX_LENGTH} caracteres.',
                'codigo_error': 'BODY_TOO_LONG',
            })
        if StaticContent.objects.filter(slug=slug).exists():
            raise ValidationError({
                'detail': 'Ya existe contenido con ese slug.',
                'codigo_error': 'SLUG_DUPLICATE',
            })
        content = StaticContent.objects.create(
            slug=slug, title=title, body=body, version=1,
        )
        StaticContentVersion.objects.create(
            content=content, version=1, title=title, body=body,
            changed_by=request.user if request.user.is_authenticated else None,
        )
        return Response(
            StaticContentSerializer(content).data, status=status.HTTP_201_CREATED,
        )


class StaticContentDetailView(_AdminOnly, APIView):
    @extend_schema(summary='Retrieve static content page.',
                   tags=['static-content'],
                   operation_id='admin_static_content_retrieve',
                   responses={200: StaticContentSerializer, 404: None})
    def get(self, request, slug):
        try:
            content = StaticContent.objects.prefetch_related('versions').get(slug=slug)
        except StaticContent.DoesNotExist:
            raise NotFound({'detail': 'Contenido no encontrado.',
                            'codigo_error': 'CONTENT_NOT_FOUND'})
        return Response(StaticContentSerializer(content).data)

    @extend_schema(summary='Edit static content page (bumps version).',
                   tags=['static-content'],
                   responses={200: StaticContentSerializer, 404: None})
    @transaction.atomic
    def patch(self, request, slug):
        try:
            content = StaticContent.objects.select_for_update().get(slug=slug)
        except StaticContent.DoesNotExist:
            raise NotFound({'detail': 'Contenido no encontrado.',
                            'codigo_error': 'CONTENT_NOT_FOUND'})

        title = request.data.get('title', content.title)
        body  = request.data.get('body',  content.body)
        if not title:
            raise ValidationError({
                'detail': 'title no puede ser vacio.',
                'codigo_error': 'TITLE_REQUIRED',
            })
        # H-CICLO31-02: mismo límite que en POST para prevenir cuerpos masivos.
        if len(body) > _BODY_MAX_LENGTH:
            raise ValidationError({
                'detail': f'body no puede superar {_BODY_MAX_LENGTH} caracteres.',
                'codigo_error': 'BODY_TOO_LONG',
            })

        content.version += 1
        content.title = title
        content.body = body
        content.save(update_fields=['title', 'body', 'version', 'updated_at'])

        StaticContentVersion.objects.create(
            content=content, version=content.version,
            title=title, body=body,
            changed_by=request.user if request.user.is_authenticated else None,
        )
        return Response(StaticContentSerializer(content).data)
