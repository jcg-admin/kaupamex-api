"""
Integration tests — UC-CFG-04 static content endpoints.
"""
import pytest

pytestmark = pytest.mark.integration


LIST_URL   = '/api/v1/admin/static-content/'
DETAIL_URL = lambda slug: f'/api/v1/admin/static-content/{slug}/'


class TestStaticContent:

    def test_anon_recibe_401(self, api_client, db):
        r = api_client.get(LIST_URL)
        assert r.status_code == 401

    def test_buyer_recibe_403(self, auth_client, db):
        r = auth_client.get(LIST_URL)
        assert r.status_code == 403

    def test_admin_crea_y_lee(self, admin_client, db):
        r = admin_client.post(LIST_URL, {
            'slug': 'privacy-policy',
            'title': 'Politica',
            'body': 'v1',
        }, format='json')
        assert r.status_code == 201
        assert r.json()['version'] == 1

        r2 = admin_client.get(DETAIL_URL('privacy-policy'))
        assert r2.status_code == 200
        assert r2.json()['title'] == 'Politica'
        assert len(r2.json()['versions']) == 1

    def test_admin_actualiza_y_bumpea_version(self, admin_client, db):
        admin_client.post(LIST_URL, {
            'slug': 'terms', 'title': 'A', 'body': 'b1',
        }, format='json')
        r = admin_client.patch(DETAIL_URL('terms'), {'body': 'b2'}, format='json')
        assert r.status_code == 200
        assert r.json()['version'] == 2
        assert len(r.json()['versions']) == 2

    def test_slug_duplicado_loud(self, admin_client, db):
        admin_client.post(LIST_URL, {
            'slug': 'about', 'title': 'About', 'body': 'x',
        }, format='json')
        r = admin_client.post(LIST_URL, {
            'slug': 'about', 'title': 'About', 'body': 'x',
        }, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'SLUG_DUPLICATE'

    def test_get_inexistente_loud_404(self, admin_client, db):
        r = admin_client.get(DETAIL_URL('does-not-exist'))
        assert r.status_code == 404
        assert r.json()['codigo_error'] == 'CONTENT_NOT_FOUND'
