"""Endpoint DRF read-only de logs técnicos (UC-ADM-06, ADR-019).

``GET /api/v2/admin/logs/`` sirve ``IrLogging`` al dashboard admin React
(``AdminLogsPage``). El contrato JSON de salida (``logger_name``, ``msg``) se
preserva sin cambios: ``_serialize`` mapea ``IrLogging.name`` /
``IrLogging.message`` a esas mismas claves.

Qué cambió con DEC-AF-11, y qué no
===================================

Este endpoint vivía en ``addons/observability`` y servía **dos fuentes**:
``?source=requestlog`` (por defecto) y ``?source=applog``. DEC-AF-11 retiró
``RequestLog`` —su mitad de error se fundió en ``ir.logging`` y su mitad de
acceso es trabajo del ``access_log`` del proxy inverso— así que sólo queda una
fuente, y el endpoint viene al addon que declara el modelo que sirve.

**El namespace y la ruta NO cambian**: sigue siendo ``admin_core_v2`` sobre
``/api/v2/admin/logs/``. La disolución de un addon no es un cambio de contrato
HTTP.

El parámetro ``source`` se conserva y **sólo admite** ``applog``, con el mismo
``400`` de antes para cualquier otro valor. Retirarlo dejaría a un cliente que
envía ``?source=requestlog`` recibiendo silenciosamente el otro registro; con
esta forma recibe un error que nombra el vocabulario vigente. Los filtros que
sólo existían para ``RequestLog`` (``status``, ``status_min``, ``path``) se
retiran con él.

- **Append-only:** sólo ``GET`` — ``APIView`` responde ``405`` al resto
  (FR-ADM-06.03).
- **Acceso:** ``IsAuthenticated`` + ``HasCapability`` (``audit.view``) → ``403``
  sin la capacidad (FR-ADM-06.04).
- **PII-safe:** ``msg`` y ``trace`` vienen scrubbed del origen (DEC-LOG-03).
- Filtros por query params + paginado a nivel DB (LIMIT/OFFSET).
"""
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz.permissions import HasCapability
from addons.base.models import IrLogging

_DEFAULT_PAGE_SIZE = 25
_MAX_PAGE_SIZE = 100
_SOURCES = ('applog',)


class AdminLogsView(APIView):
    """Feed paginado read-only de logs técnicos (UC-ADM-06)."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'audit.view'

    @extend_schema(
        summary='Listar logs tecnicos (UC-ADM-06)',
        parameters=[
            OpenApiParameter('source', str, description='applog (unica fuente desde DEC-AF-11)'),
            OpenApiParameter('correlation_id', str, description='Filtrar por correlation_id exacto'),
            OpenApiParameter('level', str, description='level exacto (INFO, ERROR, ...)'),
            OpenApiParameter('from', str, description='created_at >= (ISO 8601)'),
            OpenApiParameter('to', str, description='created_at <= (ISO 8601)'),
            OpenApiParameter('page', int, description='Numero de pagina'),
            OpenApiParameter('page_size', int, description=f'Tamano de pagina (max {_MAX_PAGE_SIZE})'),
        ],
        tags=['admin'],
    )
    def get(self, request):
        source = request.query_params.get('source', 'applog')
        if source not in _SOURCES:
            raise DRFValidationError({'source': 'Debe ser applog.'})
        page, page_size = self._pagination(request)
        qs = self._queryset(request)
        total = qs.count()
        pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        results = [self._serialize(obj) for obj in qs[start:start + page_size]]
        return Response({
            'source': source,
            'count': total,
            'page': page,
            'pages': pages,
            'results': results,
        })

    # --- paginacion / filtros ---

    def _pagination(self, request):
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except (ValueError, TypeError):
            raise DRFValidationError({'page': 'Debe ser un entero valido.'})
        try:
            page_size = int(request.query_params.get('page_size', _DEFAULT_PAGE_SIZE))
        except (ValueError, TypeError):
            raise DRFValidationError({'page_size': 'Debe ser un entero valido.'})
        page_size = max(1, min(page_size, _MAX_PAGE_SIZE))
        return page, page_size

    def _queryset(self, request):
        qs = IrLogging.objects.all().order_by('-created_at')
        correlation_id = request.query_params.get('correlation_id')
        if correlation_id:
            qs = qs.filter(correlation_id=correlation_id)
        dt_from = self._parse_dt(request, 'from')
        if dt_from is not None:
            qs = qs.filter(created_at__gte=dt_from)
        dt_to = self._parse_dt(request, 'to')
        if dt_to is not None:
            qs = qs.filter(created_at__lte=dt_to)
        level = request.query_params.get('level')
        if level:
            qs = qs.filter(level=level.upper())
        return qs

    def _parse_dt(self, request, key):
        raw = request.query_params.get(key)
        if not raw:
            return None
        dt = parse_datetime(raw)
        if dt is None:
            raise DRFValidationError({key: 'Fecha ISO 8601 invalida.'})
        # USE_TZ activo: un ISO sin offset llega naive; comparar naive contra
        # created_at (aware) lanza RuntimeWarning y es ambiguo. Lo anclamos a la
        # zona activa (H-API-LOG: filtro from/to naive bajo USE_TZ).
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt)
        return dt

    def _serialize(self, obj):
        # Claves de salida preservadas (logger_name/msg) por compat de
        # contrato con AdminLogsPage; el modelo interno es IrLogging
        # (name/message) desde DEC-08 slice 2.
        return {
            'id': obj.pk,
            'logger_name': obj.name,
            'level': obj.level,
            'msg': obj.message,
            'trace': obj.trace,
            'correlation_id': obj.correlation_id,
            'created_at': obj.created_at.isoformat(),
        }
