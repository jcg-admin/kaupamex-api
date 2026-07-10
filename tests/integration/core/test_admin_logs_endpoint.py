"""Tests de integracion — GET /api/v2/admin/logs/ (SOL-011 T-06, UC-ADM-06).

Verifican el endpoint DRF read-only del visor de logs:
  - admin (is_staff) lista RequestLog (default) y AppLog (?source=applog),
  - filtros: correlation_id, status_min, level,
  - acceso: no-staff -> 403, anonimo -> 401/403 (FR-ADM-06.04),
  - append-only: POST/PUT/DELETE -> 405 (FR-ADM-06.03),
  - paginado.

Toca DB → django_db.
"""
import pytest
from rest_framework.test import APIClient

from apps.core.models import AppLog, RequestLog
from tests.factories.user_factory import AdminUserFactory, UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

URL = '/api/v2/admin/logs/'


@pytest.fixture
def admin_client():
    client = APIClient()
    client.force_authenticate(user=AdminUserFactory())
    return client


def _seed_requestlogs():
    RequestLog.objects.create(correlation_id='c1', method='GET', path='/a',
                              status_code=200, duration_ms=5)
    RequestLog.objects.create(correlation_id='c2', method='POST', path='/b',
                              status_code=500, duration_ms=9,
                              exception_class='ValueError', error_detail='boom')


def test_admin_lists_requestlogs(admin_client):
    _seed_requestlogs()
    resp = admin_client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body['source'] == 'requestlog'
    assert body['count'] == 2
    # orden desc por created_at: la ultima creada primero
    assert body['results'][0]['path'] == '/b'
    assert body['results'][0]['exception_class'] == 'ValueError'


def test_filter_status_min(admin_client):
    _seed_requestlogs()
    resp = admin_client.get(URL, {'status_min': 400})
    assert resp.status_code == 200
    body = resp.json()
    assert body['count'] == 1
    assert body['results'][0]['status_code'] == 500


def test_filter_correlation_id(admin_client):
    _seed_requestlogs()
    resp = admin_client.get(URL, {'correlation_id': 'c1'})
    assert resp.json()['count'] == 1
    assert resp.json()['results'][0]['correlation_id'] == 'c1'


def test_source_applog_and_level_filter(admin_client):
    AppLog.objects.create(logger_name='apps.x', level='INFO', msg='hi', correlation_id='c1')
    AppLog.objects.create(logger_name='apps.x', level='ERROR', msg='boom', correlation_id='c1')
    resp = admin_client.get(URL, {'source': 'applog', 'level': 'error'})
    assert resp.status_code == 200
    body = resp.json()
    assert body['source'] == 'applog'
    assert body['count'] == 1
    assert body['results'][0]['level'] == 'ERROR'


def test_non_staff_forbidden():
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
        RequestLog.objects.create(correlation_id=f'c{i}', method='GET',
                                  path=f'/p{i}', status_code=200, duration_ms=1)
    resp = admin_client.get(URL, {'page_size': 10, 'page': 2})
    body = resp.json()
    assert body['count'] == 30
    assert body['pages'] == 3
    assert body['page'] == 2
    assert len(body['results']) == 10
