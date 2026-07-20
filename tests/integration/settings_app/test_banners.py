"""
Tests — Catálogo de banners de portada (UC-CFG-06, G-CFG-01 / G-ENV-03).

CRUD admin sobre /api/v2/admin/banners/ (BannerViewSet, capacidad
``banners.manage``) + reorder por placement, y lista pública
/api/v2/config/banners/ (PublicBannerListView, AllowAny) que sólo expone
banners activos filtrados por placement.
"""
import io

import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

from addons.website.models import Banner

pytestmark = pytest.mark.integration

ADMIN_URL   = '/api/v2/admin/banners/'
DETAIL_URL  = lambda pk: f'/api/v2/admin/banners/{pk}/'
REORDER_URL = '/api/v2/admin/banners/reorder/'
PUBLIC_URL  = '/api/v2/config/banners/'


def _png_bytes():
    buf = io.BytesIO()
    Image.new('RGB', (4, 4), color='red').save(buf, format='PNG')
    return buf.getvalue()


def _upload(name='banner.png'):
    return SimpleUploadedFile(name, _png_bytes(), content_type='image/png')


@pytest.fixture
def hero_banner(db):
    return Banner.objects.create(
        image=_upload('hero.png'), placement=Banner.Placement.HERO,
        alt_text='Hero uno', is_active=True, order=0,
    )


class TestBannersAdmin:

    # --- permisos ---
    def test_anon_recibe_401(self, api_client, db):
        assert api_client.get(ADMIN_URL).status_code == 401

    def test_comprador_recibe_403(self, auth_client, db):
        assert auth_client.get(ADMIN_URL).status_code == 403

    # --- éxito ---
    def test_admin_crea_banner(self, admin_client, db):
        r = admin_client.post(ADMIN_URL, {
            'image': _upload(),
            'placement': 'HERO',
            'alt_text': 'Promo Yoruba',
            'is_active': True,
            'order': 0,
        }, format='multipart')
        assert r.status_code == 201, r.content
        body = r.json()
        assert body['placement'] == 'HERO'
        assert body['alt_text'] == 'Promo Yoruba'
        assert body['image_url']            # URL absoluta poblada
        assert 'image' not in body          # write_only, no se expone
        assert Banner.objects.filter(placement='HERO').exists()

    def test_admin_lista_banners(self, admin_client, hero_banner, db):
        r = admin_client.get(ADMIN_URL)
        assert r.status_code == 200
        body = r.json()
        rows = body['results'] if isinstance(body, dict) and 'results' in body else body
        assert any(b['alt_text'] == 'Hero uno' for b in rows)

    def test_admin_filtra_por_placement(self, admin_client, hero_banner, db):
        Banner.objects.create(image=_upload('p.png'),
                              placement=Banner.Placement.PROMO_STRIP,
                              alt_text='Franja', is_active=True, order=0)
        r = admin_client.get(ADMIN_URL + '?placement=PROMO_STRIP')
        assert r.status_code == 200
        body = r.json()
        rows = body['results'] if isinstance(body, dict) and 'results' in body else body
        placements = {b['placement'] for b in rows}
        assert placements == {'PROMO_STRIP'}

    def test_admin_edita_banner(self, admin_client, hero_banner, db):
        r = admin_client.patch(DETAIL_URL(hero_banner.id),
                               {'alt_text': 'Editado'}, format='json')
        assert r.status_code == 200
        hero_banner.refresh_from_db()
        assert hero_banner.alt_text == 'Editado'

    def test_admin_elimina_banner(self, admin_client, hero_banner, db):
        r = admin_client.delete(DETAIL_URL(hero_banner.id))
        assert r.status_code == 204
        assert not Banner.objects.filter(pk=hero_banner.id).exists()


class TestBannersReorder:

    def test_reorder_asigna_orden_por_indice(self, admin_client, db):
        a = Banner.objects.create(image=_upload('a.png'), placement='HERO',
                                  alt_text='A', order=0)
        b = Banner.objects.create(image=_upload('b.png'), placement='HERO',
                                  alt_text='B', order=1)
        c = Banner.objects.create(image=_upload('c.png'), placement='HERO',
                                  alt_text='C', order=2)
        # nuevo orden: c, a, b
        r = admin_client.post(REORDER_URL, {'order': [c.id, a.id, b.id]},
                              format='json')
        assert r.status_code == 200, r.content
        a.refresh_from_db(); b.refresh_from_db(); c.refresh_from_db()
        assert (c.order, a.order, b.order) == (0, 1, 2)

    def test_reorder_rechaza_placement_mixto(self, admin_client, db):
        a = Banner.objects.create(image=_upload('a.png'), placement='HERO',
                                  alt_text='A', order=0)
        b = Banner.objects.create(image=_upload('b.png'),
                                  placement='PROMO_STRIP', alt_text='B', order=0)
        r = admin_client.post(REORDER_URL, {'order': [a.id, b.id]},
                              format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'MIXED_PLACEMENT_REORDER'

    def test_reorder_rechaza_id_inexistente(self, admin_client, hero_banner, db):
        r = admin_client.post(REORDER_URL, {'order': [hero_banner.id, 999999]},
                              format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'BANNER_NOT_FOUND'

    def test_reorder_rechaza_payload_invalido(self, admin_client, db):
        r = admin_client.post(REORDER_URL, {'order': []}, format='json')
        assert r.status_code == 400
        assert r.json()['codigo_error'] == 'INVALID_REORDER_PAYLOAD'

    def test_reorder_requiere_capacidad(self, auth_client, db):
        assert auth_client.post(REORDER_URL, {'order': [1]},
                                format='json').status_code == 403


class TestBannersPublic:

    def test_publico_sin_auth(self, api_client, hero_banner, db):
        assert api_client.get(PUBLIC_URL).status_code == 200

    def test_publico_solo_activos(self, api_client, db):
        Banner.objects.create(image=_upload('on.png'), placement='HERO',
                              alt_text='Visible', is_active=True, order=0)
        Banner.objects.create(image=_upload('off.png'), placement='HERO',
                              alt_text='Oculto', is_active=False, order=1)
        r = api_client.get(PUBLIC_URL)
        assert r.status_code == 200
        body = r.json()
        rows = body['results'] if isinstance(body, dict) and 'results' in body else body
        alts = {b['alt_text'] for b in rows}
        assert 'Visible' in alts
        assert 'Oculto' not in alts

    def test_publico_filtra_por_placement(self, api_client, db):
        Banner.objects.create(image=_upload('h.png'), placement='HERO',
                              alt_text='Hero', is_active=True, order=0)
        Banner.objects.create(image=_upload('p.png'), placement='PROMO_STRIP',
                              alt_text='Promo', is_active=True, order=0)
        r = api_client.get(PUBLIC_URL + '?placement=HERO')
        assert r.status_code == 200
        body = r.json()
        rows = body['results'] if isinstance(body, dict) and 'results' in body else body
        placements = {b['placement'] for b in rows}
        assert placements == {'HERO'}

    def test_publico_no_expone_campos_admin(self, api_client, hero_banner, db):
        r = api_client.get(PUBLIC_URL)
        body = r.json()
        rows = body['results'] if isinstance(body, dict) and 'results' in body else body
        assert rows, 'debe haber al menos un banner activo'
        row = rows[0]
        assert 'is_active' not in row
        assert 'created_at' not in row
        assert 'image_url' in row
