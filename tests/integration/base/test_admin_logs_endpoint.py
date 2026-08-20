"""Tests de integracion — GET /api/v2/admin/logs/ (SOL-011 T-06, UC-ADM-06).

Verifican el endpoint DRF read-only del visor de logs:

- lista ``IrLogging``, la unica fuente desde DEC-AF-11,
- filtros: ``correlation_id``, ``level``, rango ``from``/``to``,
- ``?source`` sigue validandose: ``applog`` pasa, cualquier otro valor —incluido
  el ``requestlog`` que hasta ayer era el default— da 400,
- acceso: sin la capacidad ``audit.view`` -> 403, anonimo -> 401/403 (FR-ADM-06.04),
- append-only: POST/PUT/DELETE -> 405 (FR-ADM-06.03),
- paginado.

**Reescritos con DEC-AF-11.** El endpoint servia dos fuentes; retirado
``RequestLog`` queda una, y con el se van los casos de ``status``,
``status_min`` y ``path`` —tres filtros que solo existian para las columnas de
acceso, hoy responsabilidad del ``access_log`` del proxy inverso—. El archivo
se muda a ``tests/integration/base/`` porque el endpoint vino al addon que
declara el modelo que sirve; **la URL y el namespace no cambian**.

El contrato JSON de salida (``logger_name``/``msg``) tampoco cambia: lo mapea
``AdminLogsView._serialize``.

Toca DB → ``django_db``.
"""
import pytest
from rest_framework.test import APIClient

from addons.base.models import IrLogging
from tests.factories.user_factory import AdminUserFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

URL = '/api/v2/admin/logs/'


@pytest.fixture
def admin_client():
    client = APIClient()
    client.force_authenticate(user=AdminUserFactory())
    return client


def _seed_logs():
    IrLogging.objects.create(name='apps.x', level='INFO', message='hola',
                             correlation_id='c1')
    IrLogging.objects.create(name='apps.x', level='ERROR', message='boom',
                             correlation_id='c2', trace='Traceback...')


def test_admin_lists_ir_logging(admin_client):
    _seed_logs()
    resp = admin_client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body['source'] == 'applog'
    assert body['count'] == 2
    # orden desc por created_at: la ultima creada primero
    assert body['results'][0]['msg'] == 'boom'
    assert body['results'][0]['logger_name'] == 'apps.x'
    assert body['results'][0]['trace'] == 'Traceback...'


def test_filter_correlation_id(admin_client):
    _seed_logs()
    resp = admin_client.get(URL, {'correlation_id': 'c1'})
    assert resp.json()['count'] == 1
    assert resp.json()['results'][0]['correlation_id'] == 'c1'


def test_filter_level(admin_client):
    _seed_logs()
    resp = admin_client.get(URL, {'source': 'applog', 'level': 'error'})
    assert resp.status_code == 200
    body = resp.json()
    assert body['count'] == 1
    assert body['results'][0]['level'] == 'ERROR'


def test_source_requestlog_now_400(admin_client):
    """El vocabulario vigente se nombra; no se sirve la otra fuente en silencio."""
    resp = admin_client.get(URL, {'source': 'requestlog'})
    assert resp.status_code == 400
    assert 'source' in resp.json()


def test_invalid_source_400(admin_client):
    resp = admin_client.get(URL, {'source': 'bogus'})
    assert resp.status_code == 400
    assert 'source' in resp.json()


def test_without_capability_forbidden():
    client = APIClient()
    client.force_authenticate(user=UserFactory(is_staff=False))
    assert client.get(URL).status_code == 403


def test_anonymous_denied():
    assert APIClient().get(URL).status_code in (401, 403)


def test_append_only_post_405(admin_client):
    assert admin_client.post(URL, {}, format='json').status_code == 405


def test_append_only_delete_405(admin_client):
    assert admin_client.delete(URL).status_code == 405


def test_pagination(admin_client):
    for i in range(30):
        IrLogging.objects.create(name='apps.x', level='INFO', message=f'm{i}',
                                 correlation_id=f'c{i}')
    resp = admin_client.get(URL, {'page_size': 10, 'page': 2})
    body = resp.json()
    assert body['count'] == 30
    assert body['pages'] == 3
    assert body['page'] == 2
    assert len(body['results']) == 10


def test_filter_from_to_range(admin_client):
    _seed_logs()
    # rango amplio → incluye ambos
    wide = admin_client.get(URL, {'from': '2000-01-01T00:00:00',
                                  'to': '2100-01-01T00:00:00'})
    assert wide.json()['count'] == 2
    # from en el futuro → ninguno (created_at < from)
    future = admin_client.get(URL, {'from': '2100-01-01T00:00:00'})
    assert future.json()['count'] == 0
    # to en el pasado → ninguno (created_at > to)
    past = admin_client.get(URL, {'to': '2000-01-01T00:00:00'})
    assert past.json()['count'] == 0


def test_invalid_from_iso_400(admin_client):
    _seed_logs()
    resp = admin_client.get(URL, {'from': 'not-a-date'})
    assert resp.status_code == 400
    assert 'from' in resp.json()
