"""
apps/core/middleware/request_log.py

RequestLogMiddleware (DEC-LOG-02): cobertura universal request->DB. Una fila de
RequestLog por cada request HTTP, con correlation_id (DEC-LOG-07). No bloqueante
(DEC-LOG-04): si el insert del log falla, el request continua. PII-safe
(DEC-LOG-03): solo metadata; se guarda ``user_id`` (no nombre/email) y ``path``
sin query string (evita tokens/PII en parametros).
"""
import time

from core.logging_context import (
    clear_correlation_id,
    get_request_error,
    new_correlation_id,
)
from core.models import RequestLog


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cid = new_correlation_id()
        request.correlation_id = cid
        start = time.monotonic()
        try:
            response = self.get_response(request)
        finally:
            pass
        duration_ms = int((time.monotonic() - start) * 1000)
        try:
            self._write_log(request, response, cid, duration_ms)
        except Exception:
            # silent OK because DEC-LOG-04: el logging es no-bloqueante; un
            # fallo al escribir RequestLog NUNCA debe romper el request del
            # usuario. El fallo se absorbe y el response se devuelve intacto.
            pass
        finally:
            clear_correlation_id()
        return response

    def _write_log(self, request, response, cid, duration_ms):
        user_pk = None
        user = getattr(request, 'user', None)
        if user is not None and getattr(user, 'is_authenticated', False):
            user_pk = user.pk
        view_name = ''
        match = getattr(request, 'resolver_match', None)
        if match is not None:
            view_name = match.view_name or ''
        # Campos de error (ADR-019): el custom_exception_handler de DRF sella la
        # clase de excepcion + el detalle (ya scrubbed) en el contexto; se
        # persisten solo cuando hubo excepcion (status_code >= 400).
        err = get_request_error() or {}
        RequestLog.objects.create(
            correlation_id=cid,
            method=(request.method or '')[:10],
            path=request.path[:512],
            view_name=view_name[:255],
            user_id=user_pk,
            status_code=getattr(response, 'status_code', None),
            duration_ms=duration_ms,
            ip=self._client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            exception_class=(err.get('exception_class') or '')[:255],
            error_detail=err.get('error_detail') or '',
        )

    @staticmethod
    def _client_ip(request):
        xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if xff:
            return xff.split(',')[0].strip()[:45] or None
        return request.META.get('REMOTE_ADDR') or None
