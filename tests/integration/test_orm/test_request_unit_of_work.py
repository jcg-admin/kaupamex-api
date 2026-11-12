"""Una unidad de trabajo por petición: COMMIT, señal o reversión.

≙ ``service.model.retrying`` (``odoo19c: odoo/service/model.py:160-240``) y
el despacho con base (``odoo/http.py:2267-2335``): el registro comprueba la
señalización, la vista corre en una transacción, lo pendiente del ORM se
vuelca, y la petición termina en ``commit`` + ``signal_changes()`` o en
``rollback`` + ``reset_changes()``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
request-unit-of-work.md``.
"""
import logging

import pytest
from django.apps import apps
from django.http import HttpResponse
from django.test import Client, RequestFactory, override_settings
from django.urls import path
from psycopg import errors
from django.db import OperationalError
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from addons.authz_audit.audit import audit_authz_event
from addons.authz_audit.models import AuthzEvent
from addons.base.models.ir_http import UnitOfWorkMiddleware
from orm import registry as orm_registry
from orm.environments import Environment
from orm.utils import SUPERUSER_ID
from tools.logging_handlers import DatabaseLogHandler

pytestmark = pytest.mark.django_db

SharedCompute = apps.get_model('test_orm', 'TestOrmSharedCompute')

#: Lo que la vista de la cadena real creó antes de fallar.
CHAIN_CREATED = []


class ChainFailure(Exception):
    pass


def _failing_chain_view(request):
    CHAIN_CREATED.append(_create('5->6'))
    raise ChainFailure('deshacer')


urlpatterns = [path('probe/fails', _failing_chain_view)]


@pytest.fixture
def calls(monkeypatch):
    seen = []
    for name in ('signal_changes', 'reset_changes', 'check_signaling'):
        def record(self, *args, _name=name, **kwargs):
            seen.append(_name)
            return self if _name == 'check_signaling' else None
        monkeypatch.setattr(orm_registry.Registry, name, record)
    return seen


def _create(name):
    with Environment('default', SUPERUSER_ID, {}) as env:
        return env['test_orm.shared.compute'].create({'name': name}).id


def _serve(view, path='/probe'):
    request = RequestFactory().get(path)
    middleware = UnitOfWorkMiddleware(view)
    response = middleware(request)
    return response


def test_a_good_response_commits_and_signals(calls):
    created = []

    def view(request):
        created.append(_create('2->3'))
        return HttpResponse('ok')

    assert _serve(view).status_code == 200
    assert SharedCompute.objects.filter(pk=created[0]).exists()
    assert calls == ['check_signaling', 'signal_changes']


def test_an_exception_rolls_back_and_resets(calls):
    created = []

    class Boom(Exception):
        pass

    def view(request):
        created.append(_create('4->5'))
        raise Boom('deshacer')

    middleware = UnitOfWorkMiddleware(view)
    with pytest.raises(Boom):
        middleware(RequestFactory().get('/probe'))
    assert not SharedCompute.objects.filter(pk=created[0]).exists()
    assert calls == ['check_signaling', 'reset_changes']


def test_a_drf_handled_exception_rolls_back_and_resets(calls):
    created = []

    class Probe(APIView):
        authentication_classes = ()
        permission_classes = ()

        def get(self, request):
            created.append(_create('6->7'))
            raise ValidationError('no')

    response = _serve(Probe.as_view())
    assert response.status_code == 400
    assert not SharedCompute.objects.filter(pk=created[0]).exists()
    assert calls == ['check_signaling', 'reset_changes']


def test_a_serialization_failure_is_retried(calls, monkeypatch):
    monkeypatch.setattr('addons.base.models.ir_http._retry_wait',
                        lambda attempt: 0)
    attempts = []

    def view(request):
        attempts.append(_create('8->9'))
        if len(attempts) == 1:
            raise OperationalError('retry') from errors.SerializationFailure()
        return HttpResponse('ok')

    assert _serve(view).status_code == 200
    assert not SharedCompute.objects.filter(pk=attempts[0]).exists()
    assert SharedCompute.objects.filter(pk=attempts[1]).exists()
    assert calls == ['check_signaling', 'reset_changes', 'signal_changes']


def test_pending_orm_work_reaches_the_row_before_commit(calls):
    created = []

    def view(request):
        with Environment('default', SUPERUSER_ID, {}) as env:
            record = env['test_orm.shared.compute'].create({'name': '2->5'})
            record.name = '3->6'          # recómputo pendiente
            created.append(record.id)
        return HttpResponse('ok')

    _serve(view)
    row = SharedCompute.objects.values('start', 'end').get(pk=created[0])
    assert row == {'start': 3, 'end': 6}


@override_settings(
    ROOT_URLCONF=__name__,
    MIDDLEWARE=['addons.base.models.ir_http.UnitOfWorkMiddleware'])
def test_through_the_real_handler_a_view_exception_rolls_back(calls):
    """En la cadena de Django la excepción no llega al middleware: el
    manejador llama a ``process_exception`` y devuelve un 500."""
    CHAIN_CREATED.clear()
    client = Client(raise_request_exception=False)
    assert client.get('/probe/fails').status_code == 500
    assert not SharedCompute.objects.filter(pk=CHAIN_CREATED[0]).exists()
    assert calls == ['check_signaling', 'reset_changes']


def _denials():
    return AuthzEvent.objects.filter(capability_code='probe.uow').count()


def test_a_denial_audit_survives_the_rollback():
    """≙ ``cr.postrollback``: lo encolado se escribe tras revertir."""
    def view(request):
        audit_authz_event(request, AuthzEvent.ACTION_DENY, 'probe.uow')
        raise ChainFailure('denegar')

    with pytest.raises(ChainFailure):
        _serve(view)
    assert _denials() == 1


def test_a_committed_audit_is_written_once():
    def view(request):
        audit_authz_event(request, AuthzEvent.ACTION_DENY, 'probe.uow')
        return HttpResponse('ok')

    assert _serve(view).status_code == 200
    assert _denials() == 1


def test_the_error_log_survives_the_rollback():
    """≙ el cursor propio de ``PostgreSQLHandler`` (``odoo/netsvc.py``)."""
    IrLogging = apps.get_model('base', 'IrLogging')
    handler = DatabaseLogHandler()

    def view(request):
        handler.emit(logging.makeLogRecord({
            'name': 'probe.uow', 'levelname': 'ERROR',
            'msg': 'uow-probe-error'}))
        raise ChainFailure('fallar')

    with pytest.raises(ChainFailure):
        _serve(view)
    assert IrLogging.objects.filter(message='uow-probe-error').count() == 1
