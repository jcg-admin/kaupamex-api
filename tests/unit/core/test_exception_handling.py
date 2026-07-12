"""Tests unitarios — custom_exception_handler (SOL-011 T-04, ADR-019).

Verifican que el handler:
  - delega en el handler de DRF (cuerpo de respuesta al cliente sin cambios),
  - sella exception_class + error_detail (scrubbed) en el contexto de la
    request (DEC-LOG-03),
  - es no bloqueante: un fallo al sellar no altera la respuesta (DEC-LOG-04),
  - integra con el RequestLogMiddleware: la fila RequestLog recibe los campos
    de error cuando hubo excepcion.

Toca DB en el test de integracion (RequestLog) → django_db.
"""
from unittest import mock

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from rest_framework import exceptions
from rest_framework.test import APIRequestFactory

from apps.core.exception_handling import custom_exception_handler
from apps.core.logging_context import (
    clear_correlation_id,
    get_request_error,
    set_request_error,
)
from apps.core.middleware.request_log import RequestLogMiddleware
from apps.core.models import RequestLog

pytestmark = [pytest.mark.unit]


def test_delegates_to_drf_and_seals_error():
    clear_correlation_id()
    exc = exceptions.ValidationError('invalid password=hunter2')
    ctx = {'request': APIRequestFactory().post('/x'), 'view': None}
    resp = custom_exception_handler(exc, ctx)
    # Cuerpo cliente intacto: es la respuesta 400 del handler por defecto de DRF.
    assert resp is not None
    assert resp.status_code == 400
    err = get_request_error()
    assert err['exception_class'] == 'ValidationError'
    assert 'hunter2' not in err['error_detail']
    clear_correlation_id()


def test_scrubs_error_detail():
    clear_correlation_id()
    exc = exceptions.APIException('charge failed card_token=tok_live_51H')
    custom_exception_handler(exc, {'request': APIRequestFactory().get('/x')})
    err = get_request_error()
    assert 'tok_live_51H' not in err['error_detail']
    clear_correlation_id()


def test_non_blocking_on_seal_failure():
    exc = exceptions.NotFound('missing')
    with mock.patch(
        'apps.core.exception_handling.set_request_error',
        side_effect=RuntimeError('ctx broke'),
    ):
        resp = custom_exception_handler(exc, {'request': APIRequestFactory().get('/x')})
    # La respuesta de DRF se devuelve intacta pese al fallo del sellado.
    assert resp is not None
    assert resp.status_code == 404


@pytest.mark.django_db
def test_middleware_persists_error_fields():
    def get_response(request):
        # Simula lo que hace el custom_exception_handler durante la request.
        set_request_error('ValidationError', 'campo invalido')
        return HttpResponse(status=400)

    request = RequestFactory().post('/api/v2/catalogue/products/')
    RequestLogMiddleware(get_response)(request)
    row = RequestLog.objects.get()
    assert row.status_code == 400
    assert row.exception_class == 'ValidationError'
    assert row.error_detail == 'campo invalido'


@pytest.mark.django_db
def test_middleware_no_error_fields_on_success():
    def get_response(request):
        return HttpResponse(status=200)

    request = RequestFactory().get('/api/v2/catalogue/products/')
    RequestLogMiddleware(get_response)(request)
    row = RequestLog.objects.get()
    assert row.status_code == 200
    assert row.exception_class == ''
    assert row.error_detail == ''
