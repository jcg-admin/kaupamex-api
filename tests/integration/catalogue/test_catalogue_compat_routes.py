"""
Tests — alias compat /api/v2/catalogue/* (storefront).

El UI (catalogSlice.js) consume /api/v2/catalogue/ para lista, detalle y
categorias. El backend canonico expone esas vistas bajo /api/v2/products/ y
/api/v2/categories/; compat_urls.py mapea el prefijo /api/v2/catalogue/ a las
mismas vistas. Estos tests fijan ese contrato y verifican que 'search/' NO sea
capturado como <slug> (debe seguir resolviendo a CatalogueSearchView).
"""
import pytest
from decimal import Decimal

from apps.catalogue.models import Category, Product

pytestmark = pytest.mark.integration


@pytest.fixture
def producto_publicado(db):
    cat = Category.objects.create(name='Collares', slug='collares', is_active=True)
    p = Product.objects.create(
        name='Collar Oshun dorado',
        slug='collar-oshun-dorado',
        sku='OJA-collar-oshun-dorado',
        description='Collar sagrado de Oshun.',
        short_description='Collar de Oshun.',
        price=Decimal('1250.00'),
        stock=1,
        is_active=True,
        is_published=True,
    )
    p.categories.add(cat)
    return p


def test_catalogue_list_alias(api_client, producto_publicado):
    res = api_client.get('/api/v2/catalogue/')
    assert res.status_code == 200
    slugs = [item['slug'] for item in res.json()['results']]
    assert 'collar-oshun-dorado' in slugs


def test_catalogue_categories_alias(api_client, producto_publicado):
    res = api_client.get('/api/v2/catalogue/categories/')
    assert res.status_code == 200


def test_catalogue_detail_alias(api_client, producto_publicado):
    res = api_client.get('/api/v2/catalogue/collar-oshun-dorado/')
    assert res.status_code == 200
    assert res.json()['slug'] == 'collar-oshun-dorado'


def test_catalogue_search_not_shadowed_by_slug(api_client, producto_publicado):
    # 'search/' debe resolver a CatalogueSearchView (browse_public_urls),
    # no caer en el <slug> de compat (que daria 404 buscando un producto 'search').
    res = api_client.get('/api/v2/catalogue/search/', {'q': 'oshun'})
    assert res.status_code == 200
