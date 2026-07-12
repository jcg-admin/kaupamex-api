"""
Tests — Paginas estaticas versionadas admin (UC-CFG-04).

Endpoints de settings_app (distintos del app static_content ya cubierto):
  GET  /api/v2/admin/pages/                              StaticPageAdminListView
  GET  /api/v2/admin/pages/<slug>/                       StaticPageAdminDetailView
  POST /api/v2/admin/pages/<slug>/publish/               StaticPagePublishView
  POST /api/v2/admin/pages/<slug>/versions/<v>/restore/  StaticPageRestoreView

Cubre exito (publicar/listar/detalle/restaurar con versionado), permisos
(anon 401, comprador 403) y error (slug/version inexistente 404).
"""
import pytest

from apps.settings_app.models import StaticPage, StaticPageVersion

pytestmark = pytest.mark.integration

LIST_URL       = '/api/v2/admin/pages/'
DETAIL_URL     = lambda slug: f'/api/v2/admin/pages/{slug}/'
PUBLISH_URL    = lambda slug: f'/api/v2/admin/pages/{slug}/publish/'
RESTORE_URL    = lambda slug, v: f'/api/v2/admin/pages/{slug}/versions/{v}/restore/'


class TestStaticPagesAdmin:

    # --- permisos ---
    def test_anon_recibe_401(self, api_client, db):
        r = api_client.get(LIST_URL)
        assert r.status_code == 401

    def test_comprador_recibe_403(self, auth_client, db):
        r = auth_client.get(LIST_URL)
        assert r.status_code == 403

    # --- exito: publicar crea pagina + version 1 publicada ---
    def test_admin_publica_version_inmediata(self, admin_client, db):
        r = admin_client.post(PUBLISH_URL('about'), {
            'content': 'Acerca de PracticaYoruba v1',
        }, format='json')
        assert r.status_code == 201
        body = r.json()
        assert body['version'] == 1
        assert body['status'] == StaticPageVersion.STATUS_PUBLISHED
        assert StaticPage.objects.filter(slug='about').exists()

    def test_admin_lista_paginas(self, admin_client, db):
        admin_client.post(PUBLISH_URL('terms'), {'content': 'T&C'}, format='json')
        r = admin_client.get(LIST_URL)
        assert r.status_code == 200
        slugs = [row['slug'] for row in r.json()]
        assert 'terms' in slugs

    def test_admin_detalle_incluye_version_actual(self, admin_client, db):
        admin_client.post(PUBLISH_URL('privacy'), {'content': 'Privacidad'}, format='json')
        r = admin_client.get(DETAIL_URL('privacy'))
        assert r.status_code == 200
        body = r.json()
        assert body['slug'] == 'privacy'
        assert body['current_version'] is not None
        assert body['current_version']['content'] == 'Privacidad'

    def test_segunda_publicacion_bumpea_version_y_archiva_anterior(self, admin_client, db):
        admin_client.post(PUBLISH_URL('faq'), {'content': 'v1'}, format='json')
        r2 = admin_client.post(PUBLISH_URL('faq'), {'content': 'v2'}, format='json')
        assert r2.status_code == 201
        assert r2.json()['version'] == 2
        page = StaticPage.objects.get(slug='faq')
        published = page.versions.filter(status=StaticPageVersion.STATUS_PUBLISHED)
        # Solo la ultima version queda publicada.
        assert published.count() == 1
        assert published.first().version == 2

    def test_restaurar_version_anterior_crea_nueva_publicada(self, admin_client, db):
        admin_client.post(PUBLISH_URL('returns'), {'content': 'original'}, format='json')
        admin_client.post(PUBLISH_URL('returns'), {'content': 'cambiada'}, format='json')
        r = admin_client.post(RESTORE_URL('returns', 1), format='json')
        assert r.status_code == 201
        body = r.json()
        # Restaurar v1 crea v3 con el contenido de v1, publicada.
        assert body['version'] == 3
        assert body['content'] == 'original'
        assert body['status'] == StaticPageVersion.STATUS_PUBLISHED

    # --- errores ---
    def test_detalle_slug_inexistente_404(self, admin_client, db):
        r = admin_client.get(DETAIL_URL('terms'))
        assert r.status_code == 404

    def test_restaurar_version_inexistente_404(self, admin_client, db):
        admin_client.post(PUBLISH_URL('about'), {'content': 'v1'}, format='json')
        r = admin_client.post(RESTORE_URL('about', 99), format='json')
        assert r.status_code == 404


PUBLIC_URL = lambda slug: f'/api/v2/config/pages/{slug}/'


class TestStaticPagesPublic:
    """Endpoint público /api/v2/config/pages/<slug>/ (H-UI-CFG04-01).

    Permite que el storefront /info consuma lo que el admin publica en vez de
    un módulo hardcodeado. AllowAny; sólo expone la versión PUBLISHED.
    """

    def test_publico_devuelve_contenido_publicado(self, api_client, admin_client, db):
        admin_client.post(PUBLISH_URL('faq'), {'content': '<p>Preguntas</p>'}, format='json')
        r = api_client.get(PUBLIC_URL('faq'))
        assert r.status_code == 200
        body = r.json()
        assert body['slug'] == 'faq'
        assert body['content'] == '<p>Preguntas</p>'
        # No filtra campos admin (versiones/estado internos).
        assert 'current_version' not in body

    def test_publico_es_anonimo(self, api_client, admin_client, db):
        admin_client.post(PUBLISH_URL('about'), {'content': 'x'}, format='json')
        # Sin autenticar: 200 (AllowAny), no 401.
        assert api_client.get(PUBLIC_URL('about')).status_code == 200

    def test_publico_404_sin_pagina(self, api_client, db):
        assert api_client.get(PUBLIC_URL('terms')).status_code == 404

    def test_publico_404_sin_version_publicada(self, api_client, admin_client, db):
        # Publica programada (con publish_at futuro) → queda DRAFT, sin PUBLISHED.
        admin_client.post(PUBLISH_URL('returns'), {
            'content': 'Devoluciones', 'publish_at': '2999-01-01T00:00:00Z',
        }, format='json')
        assert api_client.get(PUBLIC_URL('returns')).status_code == 404
