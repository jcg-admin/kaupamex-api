"""
Integration tests — P-17 search history endpoints (UC-SRCH-03).
"""
import pytest
from apps.search_history.models import SearchEntry
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.integration


LIST_URL   = '/api/v2/search/history/'
DETAIL_URL = lambda pk: f'/api/v2/search/history/{pk}/'


@pytest.fixture
def entries(db, user):
    out = []
    for i in range(3):
        out.append(SearchEntry.objects.create(
            user=user, query=f'q{i}', normalized_query=f'q{i}',
            results_count=i,
        ))
    return out


class TestSearchHistory:

    def test_lista_solo_propias_20_max(self, auth_client, user, db):
        other = get_user_model().objects.create_user(
            username='otherSH', email='osh@sh.com', password='x',
        )
        SearchEntry.objects.create(
            user=other, query='ajeno', normalized_query='ajeno', results_count=0,
        )
        for i in range(25):
            SearchEntry.objects.create(
                user=user, query=f't{i}', normalized_query=f't{i}', results_count=i,
            )
        r = auth_client.get(LIST_URL)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 20
        queries = {e['query'] for e in data}
        assert 'ajeno' not in queries

    def test_lista_requiere_auth(self, api_client, db):
        r = api_client.get(LIST_URL)
        assert r.status_code == 401

    def test_delete_all(self, auth_client, user, entries, db):
        r = auth_client.delete(LIST_URL)
        assert r.status_code == 204
        assert SearchEntry.objects.filter(user=user).count() == 0

    def test_delete_single(self, auth_client, user, entries, db):
        r = auth_client.delete(DETAIL_URL(entries[0].id))
        assert r.status_code == 204
        assert not SearchEntry.objects.filter(pk=entries[0].id).exists()

    def test_delete_ajeno_devuelve_404_loud(self, auth_client, db):
        other = get_user_model().objects.create_user(
            username='oshd', email='oshd@sh.com', password='x',
        )
        e = SearchEntry.objects.create(
            user=other, query='x', normalized_query='x', results_count=0,
        )
        r = auth_client.delete(DETAIL_URL(e.id))
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'ENTRY_NOT_FOUND'
