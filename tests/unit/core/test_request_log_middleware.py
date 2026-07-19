"""Tests unitarios — RequestLogMiddleware (SOL-011, DEC-LOG-02).

Verifican que el middleware:
  - crea una fila RequestLog por request con metadata (method, path,
    status_code, duration_ms, correlation_id),
  - fija request.correlation_id y lo limpia al terminar (DEC-LOG-07),
  - es PII-safe: guarda user_id (no email/nombre) y path sin query string
    (DEC-LOG-03),
  - es no bloqueante: si el insert del log falla, el request continua
    (DEC-LOG-04),
  - extrae la IP del cliente respetando X-Forwarded-For.

Toca DB (RequestLog.objects.create) → pytest.mark.django_db.
"""
from unittest import mock

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from addons.observability.middleware import RequestLogMiddleware
from addons.observability.models import RequestLog
from tools.logging_context import get_correlation_id
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _middleware(status=200):
    def get_response(request):
        # correlation_id ya debe estar disponible dentro del request.
        assert getattr(request, 'correlation_id', None)
        assert get_correlation_id() == request.correlation_id
        return HttpResponse(status=status)

    return RequestLogMiddleware(get_response)


def test_creates_one_row_per_request():
    request = RequestFactory().get('/api/v2/catalogue/products/')
    response = _middleware(status=200)(request)

    assert response.status_code == 200
    assert RequestLog.objects.count() == 1
    log = RequestLog.objects.get()
    assert log.method == 'GET'
    assert log.path == '/api/v2/catalogue/products/'
    assert log.status_code == 200
    assert log.duration_ms is not None and log.duration_ms >= 0
    assert len(log.correlation_id) == 32


def test_sets_and_clears_correlation_id():
    request = RequestFactory().get('/x/')
    _middleware()(request)
    # request lo conserva; el contexto se limpia al terminar (DEC-LOG-07).
    assert getattr(request, 'correlation_id', None)
    assert get_correlation_id() is None


def test_path_excludes_query_string():
    # RequestFactory separa la query string en request.path vs META, pero
    # verificamos explicitamente que no se guarda ningun '?token=...'.
    request = RequestFactory().get('/api/v2/pay/?token=secret&card=4111')
    _middleware()(request)
    log = RequestLog.objects.get()
    assert '?' not in log.path
    assert 'secret' not in log.path


def test_anonymous_user_id_is_null():
    request = RequestFactory().get('/x/')
    _middleware()(request)
    assert RequestLog.objects.get().user_id is None


def test_authenticated_stores_user_fk_not_pii():
    # FK dura → el usuario debe existir realmente (DEC-LOG-03 nivel 2).
    user = UserFactory(email='buyer@example.com')
    request = RequestFactory().get('/x/')
    request.user = user
    _middleware()(request)
    log = RequestLog.objects.get()
    assert log.user_id == user.pk
    # PII-safe: el email NO se persiste en ninguna columna de texto del log.
    assert 'buyer@example.com' not in (log.user_agent + log.path + log.view_name)


def test_client_ip_prefers_x_forwarded_for():
    request = RequestFactory().get('/x/', HTTP_X_FORWARDED_FOR='203.0.113.9, 10.0.0.1')
    _middleware()(request)
    assert RequestLog.objects.get().ip == '203.0.113.9'


def test_falls_back_to_remote_addr():
    request = RequestFactory().get('/x/', REMOTE_ADDR='198.51.100.7')
    _middleware()(request)
    assert RequestLog.objects.get().ip == '198.51.100.7'


def test_non_blocking_when_log_write_fails():
    # DEC-LOG-04: si el insert falla, el request NO se rompe.
    request = RequestFactory().get('/x/')
    with mock.patch.object(RequestLog.objects, 'create',
                           side_effect=Exception('db down')):
        response = _middleware(status=201)(request)
    assert response.status_code == 201
    assert RequestLog.objects.count() == 0
    # el contexto igual se limpia pese al fallo.
    assert get_correlation_id() is None
