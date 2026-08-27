"""Superficie de páginas estáticas versionadas — ``website`` (UC-CFG-04).

Porte de la capa HTTP del ex-addon ``settings_app`` (retirado en
``api@115d219``); los modelos ya vivían en ``website/models/static_page.py``.
La referencia hospeda las páginas del sitio en ``website`` — su admin es el
web client, no REST, así que la forma de la superficie es **nuestra**
(``admin_urls`` por addon, precedente ya montado en ``observability``,
``sale_management``, ``helpdesk``, ``loyalty``, ``website``).

Las páginas son contenido del sitio, no filas per-company: ``StaticPage`` no
declara ``company``, así que el canal del dato (``ir.rule`` vía
``RuleScopedManager``) no aplica aquí y el gate es la capacidad ``settings``.
La elevación (``su``) no se usa en ninguna de estas vistas.
"""
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz.permissions import HasCapability
from addons.website.controllers.serializers import (
    PublicStaticPageSerializer,
    StaticPagePublishSerializer,
    StaticPageRestorationSerializer,
    StaticPageSerializer,
    StaticPageVersionSerializer,
)
from addons.website.models import StaticPage, StaticPageVersion
from config.schema import error_response


class _PageAdmin:
    permission_classes = [IsAuthenticated, HasCapability]


class StaticPageAdminListView(_PageAdmin, APIView):
    """GET ``/api/v2/admin/pages/`` — listado de páginas (FR-CFG-04.02)."""

    required_capability = 'settings.view'
    serializer_class = StaticPageSerializer

    @extend_schema(summary='Listar páginas estáticas (UC-CFG-04)',
                   tags=['admin-pages'],
                   operation_id='admin_pages_list',
                   responses={200: StaticPageSerializer(many=True)})
    def get(self, request):
        pages = StaticPage.objects.prefetch_related('versions').all()
        return Response(StaticPageSerializer(pages, many=True).data)


class StaticPageAdminDetailView(_PageAdmin, APIView):
    """GET ``/api/v2/admin/pages/<slug>/`` — detalle con versión activa."""

    required_capability = 'settings.view'
    serializer_class = StaticPageSerializer

    @extend_schema(summary='Detalle de página estática (UC-CFG-04)',
                   tags=['admin-pages'],
                   operation_id='admin_pages_retrieve',
                   responses={200: StaticPageSerializer,
                              404: error_response('Página no encontrada')})
    def get(self, request, slug):
        try:
            page = StaticPage.objects.prefetch_related('versions').get(slug=slug)
        except StaticPage.DoesNotExist:
            return Response({'detail': 'Página no encontrada.',
                             'codigo_error': 'PAGE_NOT_FOUND'}, status=404)
        return Response(StaticPageSerializer(page).data)


class StaticPageStatusV2View(_PageAdmin, APIView):
    """PATCH ``/api/v2/admin/pages/<slug>/status/`` — publica una versión nueva.

    Publicar es un cambio de estado del contenido: v1 lo modelaba como
    ``POST /publish/``; v2 lo expone como transición sobre el recurso.
    """

    required_capability = 'settings.edit'
    serializer_class = StaticPagePublishSerializer

    @extend_schema(summary='Publicar nueva versión de página estática (UC-CFG-04)',
                   tags=['admin-pages'],
                   request=StaticPagePublishSerializer,
                   responses={201: StaticPageVersionSerializer})
    def patch(self, request, slug):
        page, _ = StaticPage.objects.get_or_create(
            slug=slug,
            defaults={'title': dict(StaticPage.PAGE_CHOICES).get(slug, slug)},
        )
        payload = StaticPagePublishSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        publish_at = payload.validated_data.get('publish_at')
        is_immediate = not publish_at

        # H-CICLO92-01: serializar publicaciones concurrentes del mismo slug —
        # sin el lock dos peticiones calculan el mismo next_version y una
        # revienta con IntegrityError (unique_together page+version).
        with transaction.atomic():
            page = StaticPage.objects.select_for_update().get(pk=page.pk)

            if is_immediate:
                StaticPageVersion.objects.filter(
                    page=page, status=StaticPageVersion.STATUS_PUBLISHED,
                ).update(status=StaticPageVersion.STATUS_ARCHIVED,
                         updated_at=timezone.now())

            last = page.versions.order_by('-version').first()
            version = StaticPageVersion.objects.create(
                page=page,
                version=(last.version + 1) if last else 1,
                content=payload.validated_data['content'],
                status=(StaticPageVersion.STATUS_PUBLISHED if is_immediate
                        else StaticPageVersion.STATUS_DRAFT),
                created_by=request.user,
                publish_at=publish_at,
            )
        return Response(StaticPageVersionSerializer(version).data, status=201)


class StaticPageRestorationV2View(_PageAdmin, APIView):
    """POST ``/api/v2/admin/pages/<slug>/restorations/`` — revertir a una versión.

    v1 llevaba el número de versión en la ruta
    (``/versions/<v>/restore/``); v2 lo toma del cuerpo, porque la
    restauración **crea** un recurso nuevo (la versión restaurada).
    """

    required_capability = 'settings.edit'
    serializer_class = StaticPageRestorationSerializer

    @extend_schema(summary='Revertir página estática a una versión (UC-CFG-04)',
                   tags=['admin-pages'],
                   request=StaticPageRestorationSerializer,
                   responses={201: StaticPageVersionSerializer,
                              400: error_response('VERSION_REQUIRED · INVALID_VERSION'),
                              404: error_response('Versión no encontrada')})
    def post(self, request, slug):
        version_raw = request.data.get('version')
        if version_raw is None:
            return Response(
                {'detail': 'version requerido.', 'codigo_error': 'VERSION_REQUIRED'},
                status=400,
            )
        try:
            version = int(version_raw)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'version debe ser un entero.', 'codigo_error': 'INVALID_VERSION'},
                status=400,
            )

        try:
            old = StaticPageVersion.objects.select_related('page').get(
                page__slug=slug, version=version,
            )
        except StaticPageVersion.DoesNotExist:
            return Response({'detail': 'Versión no encontrada.',
                             'codigo_error': 'VERSION_NOT_FOUND'}, status=404)

        with transaction.atomic():
            page = StaticPage.objects.select_for_update().get(pk=old.page_id)

            StaticPageVersion.objects.filter(
                page=page, status=StaticPageVersion.STATUS_PUBLISHED,
            ).update(status=StaticPageVersion.STATUS_ARCHIVED,
                     updated_at=timezone.now())

            last = page.versions.order_by('-version').first()
            restored = StaticPageVersion.objects.create(
                page=page,
                version=last.version + 1,
                content=old.content,
                status=StaticPageVersion.STATUS_PUBLISHED,
                created_by=request.user,
            )
        return Response(StaticPageVersionSerializer(restored).data, status=201)


class PublicStaticPageView(APIView):
    """GET ``/api/v2/config/pages/<slug>/`` — contenido público de una página.

    UC-CFG-04 (H-UI-CFG04-01): el storefront (``/info/:slug``) consume lo que
    el admin edita. 404 si la página no existe o no tiene versión publicada —
    el frontend cae a su contenido por defecto.
    """

    permission_classes = [AllowAny]
    serializer_class = PublicStaticPageSerializer
    # ≙ website=True en ``odoo19c: addons/website/controllers/main.py:344``
    # (``/website/info`` — página pública de contenido del sitio)
    is_frontend = True

    @extend_schema(summary='Contenido público de página estática (UC-CFG-04)',
                   tags=['config'],
                   operation_id='public_pages_retrieve',
                   responses={200: PublicStaticPageSerializer,
                              404: error_response('Página no encontrada o sin publicar')})
    def get(self, request, slug):
        try:
            page = StaticPage.objects.prefetch_related('versions').get(slug=slug)
        except StaticPage.DoesNotExist:
            return Response({'detail': 'Página no encontrada.',
                             'codigo_error': 'PAGE_NOT_FOUND'}, status=404)
        if page.current_version is None:
            return Response({'detail': 'Página sin versión publicada.',
                             'codigo_error': 'PAGE_NOT_PUBLISHED'}, status=404)
        return Response(PublicStaticPageSerializer(page).data)
