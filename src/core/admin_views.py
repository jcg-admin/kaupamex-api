"""
apps/core/admin_views.py

Endpoint DRF read-only de logs tecnicos (SOL-011 T-06, UC-ADM-06, DEC-LOG-08
revisada, ADR-019). ``GET /api/v2/admin/logs/`` sirve ``RequestLog`` (default) y
``IrLogging`` (``?source=applog``) al dashboard admin React (``AdminLogsPage``,
T-09).

``IrLogging`` (``ir.logging``, ``addons.base``) reemplaza a ``core.AppLog``
desde DEC-08 slice 2. El contrato JSON de este endpoint (``logger_name``,
``msg``) se preserva sin cambios para no romper al consumidor
(``AdminLogsPage``): ``_serialize_applog`` mapea ``IrLogging.name`` /
``IrLogging.message`` a esas mismas claves de salida.

``RequestLog`` vive en ``addons.observability`` (addon net-new, DEC-12) desde
el slice 3 (antes ``core.models``); el contrato JSON del endpoint no cambia.

- Reemplaza al Django admin (H-API-LOG-01: gated tras ``DJANGO_ADMIN_ENABLED``,
  deshabilitado en prod). Es el patron ``apps/<app>/admin_urls.py`` del proyecto.
- **Append-only:** solo ``GET`` — ``APIView`` responde ``405`` a
  ``POST``/``PUT``/``PATCH``/``DELETE`` (FR-ADM-06.03).
- **Acceso:** ``IsAuthenticated`` + ``HasCapability`` (``audit.view``) → ``403``
  sin la capacidad (FR-ADM-06.04). ``is_staff`` ya no existe (party/authz).
- **PII-safe:** el modelo ya no persiste PII (Nivel 2 se referencia via
  ``user_id``); ``msg`` / ``trace`` / ``error_detail`` vienen scrubbed del
  origen (DEC-LOG-03).
- Filtros por query params + paginado a nivel DB (LIMIT/OFFSET).
- Nivel 0 preservado (DEC-LOG-06): DRF es framework, no un modulo de dominio.
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
from addons.observability.models import RequestLog

_DEFAULT_PAGE_SIZE = 25
_MAX_PAGE_SIZE = 100
_SOURCES = ('requestlog', 'applog')


class AdminLogsView(APIView):
    """Feed paginado read-only de logs tecnicos (UC-ADM-06)."""

    permission_classes = [IsAuthenticated, HasCapability]
    required_capability = 'audit.view'

    @extend_schema(
        summary='Listar logs tecnicos (UC-ADM-06)',
        parameters=[
            OpenApiParameter('source', str, description='requestlog (default) | applog'),
            OpenApiParameter('correlation_id', str, description='Filtrar por correlation_id exacto'),
            OpenApiParameter('status', int, description='RequestLog: status_code exacto'),
            OpenApiParameter('status_min', int, description='RequestLog: status_code >= (ej. 400)'),
            OpenApiParameter('path', str, description='RequestLog: path contiene'),
            OpenApiParameter('level', str, description='IrLogging: level exacto (INFO, ERROR, ...)'),
            OpenApiParameter('from', str, description='created_at >= (ISO 8601)'),
            OpenApiParameter('to', str, description='created_at <= (ISO 8601)'),
            OpenApiParameter('page', int, description='Numero de pagina'),
            OpenApiParameter('page_size', int, description=f'Tamano de pagina (max {_MAX_PAGE_SIZE})'),
        ],
        tags=['admin'],
    )
    def get(self, request):
        source = request.query_params.get('source', 'requestlog')
        if source not in _SOURCES:
            raise DRFValidationError({'source': 'Debe ser requestlog o applog.'})
        page, page_size = self._pagination(request)
        qs = (self._requestlog_qs(request) if source == 'requestlog'
              else self._applog_qs(request))
        total = qs.count()
        pages = max(1, (total + page_size - 1) // page_size)
        start = (page - 1) * page_size
        serialize = (self._serialize_requestlog if source == 'requestlog'
                     else self._serialize_applog)
        results = [serialize(obj) for obj in qs[start:start + page_size]]
        return Response({
            'source': source,
            'count': total,
            'page': page,
            'pages': pages,
            'results': results,
        })

    # --- paginacion / filtros comunes ---

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

    def _apply_common(self, request, qs):
        correlation_id = request.query_params.get('correlation_id')
        if correlation_id:
            qs = qs.filter(correlation_id=correlation_id)
        dt_from = self._parse_dt(request, 'from')
        if dt_from is not None:
            qs = qs.filter(created_at__gte=dt_from)
        dt_to = self._parse_dt(request, 'to')
        if dt_to is not None:
            qs = qs.filter(created_at__lte=dt_to)
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

    # --- RequestLog ---

    def _requestlog_qs(self, request):
        qs = RequestLog.objects.all().order_by('-created_at')
        qs = self._apply_common(request, qs)
        status = request.query_params.get('status')
        if status:
            try:
                qs = qs.filter(status_code=int(status))
            except (ValueError, TypeError):
                raise DRFValidationError({'status': 'Debe ser un entero valido.'})
        status_min = request.query_params.get('status_min')
        if status_min:
            try:
                qs = qs.filter(status_code__gte=int(status_min))
            except (ValueError, TypeError):
                raise DRFValidationError({'status_min': 'Debe ser un entero valido.'})
        path = request.query_params.get('path')
        if path:
            qs = qs.filter(path__icontains=path)
        return qs

    def _serialize_requestlog(self, obj):
        return {
            'id': obj.pk,
            'correlation_id': obj.correlation_id,
            'method': obj.method,
            'path': obj.path,
            'view_name': obj.view_name,
            'status_code': obj.status_code,
            'duration_ms': obj.duration_ms,
            'user_id': obj.user_id,
            'ip': str(obj.ip) if obj.ip else None,
            'user_agent': obj.user_agent,
            'exception_class': obj.exception_class,
            'error_detail': obj.error_detail,
            'created_at': obj.created_at.isoformat(),
        }

    # --- IrLogging (fuente ?source=applog) ---

    def _applog_qs(self, request):
        qs = IrLogging.objects.all().order_by('-created_at')
        qs = self._apply_common(request, qs)
        level = request.query_params.get('level')
        if level:
            qs = qs.filter(level=level.upper())
        return qs

    def _serialize_applog(self, obj):
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
