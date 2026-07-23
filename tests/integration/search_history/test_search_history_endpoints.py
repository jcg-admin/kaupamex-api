"""
Integration tests — P-17 search history endpoints (UC-SRCH-03).
"""
import pytest
from addons.catalogue.models import SearchHistory
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.integration


LIST_URL   = '/api/v2/search/history/'
DETAIL_URL = lambda pk: f'/api/v2/search/history/{pk}/'


@pytest.fixture
def entries(db, user):
    out = []
    for i in range(3):
        out.append(SearchHistory.objects.create(
            user=user, term=f'q{i}',
        ))
    return out


class TestSearchHistory:

    def test_lista_solo_propias_20_max(self, auth_client, user, db):
        other = get_user_model().objects.create_user(
            email='osh@sh.com', password='x',
        )
        SearchHistory.objects.create(user=other, term='ajeno')
        for i in range(25):
            SearchHistory.objects.create(user=user, term=f't{i}')
        r = auth_client.get(LIST_URL)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 20
        terms = {e['term'] for e in data}
        assert 'ajeno' not in terms

    def test_lista_requiere_auth(self, api_client, db):
        r = api_client.get(LIST_URL)
        assert r.status_code == 401

    def test_delete_all(self, auth_client, user, entries, db):
        r = auth_client.delete(LIST_URL)
        assert r.status_code == 204
        assert SearchHistory.objects.filter(user=user).count() == 0

    def test_delete_single(self, auth_client, user, entries, db):
        r = auth_client.delete(DETAIL_URL(entries[0].id))
        assert r.status_code == 204
        assert not SearchHistory.objects.filter(pk=entries[0].id).exists()

    def test_delete_ajeno_devuelve_404_loud(self, auth_client, db):
        other = get_user_model().objects.create_user(
            email='oshd@sh.com', password='x',
        )
        e = SearchHistory.objects.create(user=other, term='x')
        r = auth_client.delete(DETAIL_URL(e.id))
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'ENTRY_NOT_FOUND'
