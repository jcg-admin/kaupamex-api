"""
Tests unitarios del management command import_catalog_oja.

Usa tmp_path (pytest) para crear un catálogo mínimo en disco
sin tocar /tmp/catalogo/oja/. Tests aislados de filesystem real.

BD: kaupamex_qa (config.settings.testing)
"""
import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.management import call_command

from addons.catalogue.models import Category, Product, ProductImage
from addons.catalogue.management.commands.import_catalog_oja import (
    _clean_description,
    CATEGORY_NAMES,
    SLUG_OVERRIDES,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_product_dir(cat_dir: Path, slug: str, data: dict) -> Path:
    """Crea {cat_dir}/{slug}/data.json con los datos dados."""
    prod_dir = cat_dir / slug
    prod_dir.mkdir(parents=True, exist_ok=True)
    (prod_dir / 'data.json').write_text(json.dumps(data), encoding='utf-8')
    (prod_dir / 'images').mkdir(exist_ok=True)
    return prod_dir


def _minimal_product(slug: str, precio: float = 100.0, descripcion: str = 'Desc') -> dict:
    return {
        'slug': slug,
        'nombre': f'Producto {slug}',
        'descripcion': descripcion,
        'precio_actual': precio,
        'imagenes': [],
    }


@pytest.fixture
def catalog_dir(tmp_path):
    """Catálogo mínimo con dos categorías y un producto cada una."""
    col = tmp_path / 'collares-y-pulseras'
    col.mkdir()
    _make_product_dir(col, 'collar-azul', _minimal_product('collar-azul', 350.0))

    ens = tmp_path / 'enseres'
    ens.mkdir()
    _make_product_dir(ens, 'aceite-oya', _minimal_product('aceite-oya', 85.0))

    return tmp_path


# ---------------------------------------------------------------------------
# Pruebas de funciones puras
# ---------------------------------------------------------------------------

class TestLimpiarDescripcion:
    """_clean_description corta en los marcadores correctos."""

    def test_corta_en_recibelo(self):
        texto = 'Descripción real. Recibelo: basura extra'
        assert _clean_description(texto) == 'Descripción real.'

    def test_corta_en_valoraciones(self):
        texto = 'Producto especial. Valoraciones de clientes aquí'
        assert _clean_description(texto) == 'Producto especial.'

    def test_corta_en_informacion_adicional(self):
        texto = 'Texto útil. Información adicional no relevante'
        assert _clean_description(texto) == 'Texto útil.'

    def test_sin_marcador_devuelve_completo(self):
        texto = 'Descripción limpia sin marcadores.'
        assert _clean_description(texto) == texto

    def test_texto_vacio_devuelve_vacio(self):
        assert _clean_description('') == ''

    def test_none_devuelve_vacio(self):
        assert _clean_description(None) == ''


class TestConstantes:
    """CATEGORY_NAMES y SLUG_OVERRIDES tienen los valores esperados."""

    def test_enseres_tiene_nombre_correcto(self):
        assert CATEGORY_NAMES['enseres'] == 'Ingredientes Rituales'

    def test_slug_override_enseres(self):
        assert SLUG_OVERRIDES['enseres'] == 'ingredientes-rituales'

    def test_ocho_categorias_mapeadas(self):
        assert len(CATEGORY_NAMES) == 8

    def test_todos_los_slugs_override_tienen_entry_en_nombres(self):
        for folder_slug in SLUG_OVERRIDES:
            assert folder_slug in CATEGORY_NAMES


# ---------------------------------------------------------------------------
# Pruebas de creación de categorías
# ---------------------------------------------------------------------------

class TestImportCatalogOjaCategory:
    """El command crea categorías con slug y nombre correctos."""

    def test_categoria_creada(self, db, catalog_dir):
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))

        cat = Category.objects.get(slug='collares-y-pulseras')
        assert cat.name == 'Collares y Pulseras'
        assert cat.is_active is True

    def test_categoria_idempotente(self, db, catalog_dir):
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))

        assert Category.objects.filter(slug='collares-y-pulseras').count() == 1

    def test_slug_override_enseres(self, db, catalog_dir):
        """La carpeta 'enseres' genera slug 'ingredientes-rituales', no 'enseres'."""
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))

        assert not Category.objects.filter(slug='enseres').exists()
        cat = Category.objects.get(slug='ingredientes-rituales')
        assert cat.name == 'Ingredientes Rituales'

    def test_carpeta_desconocida_ignorada(self, db, tmp_path):
        """Una carpeta cuyo nombre no está en CATEGORY_NAMES se ignora."""
        (tmp_path / 'carpeta-desconocida').mkdir()
        call_command('import_catalog_oja', catalog_dir=str(tmp_path))

        assert Category.objects.filter(slug='carpeta-desconocida').count() == 0

    def test_archivos_no_son_categorias(self, db, tmp_path):
        """Archivos en el nivel de catálogo (_resumen.json) se ignoran."""
        (tmp_path / '_resumen.json').write_text('{}', encoding='utf-8')
        col = tmp_path / 'collares-y-pulseras'
        col.mkdir()
        _make_product_dir(col, 'collar-x', _minimal_product('collar-x'))
        call_command('import_catalog_oja', catalog_dir=str(tmp_path))

        assert Category.objects.filter(slug='collares-y-pulseras').count() == 1


# ---------------------------------------------------------------------------
# Pruebas de creación de productos
# ---------------------------------------------------------------------------

class TestImportCatalogOjaProduct:
    """El command crea productos con los campos correctos."""

    def test_producto_creado(self, db, catalog_dir):
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))

        assert Product.objects.filter(slug='collar-azul').exists()

    def test_sku_prefijo_oja(self, db, catalog_dir):
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))

        product = Product.objects.get(slug='collar-azul')
        assert product.sku == 'OJA-collar-azul'

    def test_precio_es_decimal(self, db, catalog_dir):
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))

        product = Product.objects.get(slug='collar-azul')
        assert isinstance(product.price, Decimal)
        assert product.price == Decimal('350.00')

    def test_precio_decimal_con_centavos(self, db, tmp_path):
        """Precios float con decimales se convierten sin error IEEE 754."""
        col = tmp_path / 'collares-y-pulseras'
        col.mkdir()
        _make_product_dir(col, 'collar-centavos', _minimal_product('collar-centavos', 3835.15))
        call_command('import_catalog_oja', catalog_dir=str(tmp_path))

        product = Product.objects.get(slug='collar-centavos')
        assert product.price == Decimal('3835.15')

    def test_stock_inicial_diez(self, db, catalog_dir):
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))

        product = Product.objects.get(slug='collar-azul')
        assert product.stock == 10

    def test_reimport_no_pisa_stock(self, db, catalog_dir):
        """Un re-import debe preservar el stock ajustado, no resetearlo."""
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))
        product = Product.objects.get(slug='collar-azul')
        product.stock = 3
        product.save(update_fields=['stock'])

        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))

        product.refresh_from_db()
        assert product.stock == 3

    def test_producto_activo_y_publicado(self, db, catalog_dir):
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))

        product = Product.objects.get(slug='collar-azul')
        assert product.is_active is True
        assert product.is_published is True

    def test_descripcion_truncada_en_recibelo(self, db, tmp_path):
        col = tmp_path / 'collares-y-pulseras'
        col.mkdir()
        _make_product_dir(col, 'collar-desc', _minimal_product(
            'collar-desc',
            descripcion='Collar ritual. Recibelo: texto basura de la tienda'
        ))
        call_command('import_catalog_oja', catalog_dir=str(tmp_path))

        product = Product.objects.get(slug='collar-desc')
        assert 'Recibelo' not in product.description
        assert product.description == 'Collar ritual.'

    def test_producto_asignado_a_categoria_correcta(self, db, catalog_dir):
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))

        product = Product.objects.get(slug='collar-azul')
        assert product.categories.first().slug == 'collares-y-pulseras'

    def test_producto_enseres_asignado_a_ingredientes_rituales(self, db, catalog_dir):
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))

        product = Product.objects.get(slug='aceite-oya')
        assert product.categories.first().slug == 'ingredientes-rituales'

    def test_producto_idempotente(self, db, catalog_dir):
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir))

        assert Product.objects.filter(slug='collar-azul').count() == 1


# ---------------------------------------------------------------------------
# Pruebas de imágenes
# ---------------------------------------------------------------------------

class TestImportCatalogOjaImages:
    """El command crea ProductImage y copia archivos a MEDIA_ROOT."""

    def test_imagen_cover_creada(self, db, tmp_path, settings):
        settings.MEDIA_ROOT = str(tmp_path / 'media')
        col = tmp_path / 'collares-y-pulseras'
        col.mkdir()
        prod_dir = _make_product_dir(col, 'collar-img', _minimal_product(
            'collar-img',
            descripcion='Desc',
        ))
        # Crear imagen de prueba
        img_file = prod_dir / 'images' / 'collar-img.png'
        img_file.write_bytes(b'\x89PNG\r\n\x1a\n')  # header PNG mínimo

        data = _minimal_product('collar-img')
        data['imagenes'] = [{'archivo': 'collar-img.png'}]
        (prod_dir / 'data.json').write_text(json.dumps(data), encoding='utf-8')

        call_command('import_catalog_oja', catalog_dir=str(tmp_path))

        product = Product.objects.get(slug='collar-img')
        img = ProductImage.objects.get(product=product, order=0)
        assert img.is_cover is True
        assert img.image == 'products/images/collar-img.png'

    def test_imagen_copiada_a_media_root(self, db, tmp_path, settings):
        media = tmp_path / 'media'
        settings.MEDIA_ROOT = str(media)
        col = tmp_path / 'collares-y-pulseras'
        col.mkdir()
        prod_dir = _make_product_dir(col, 'collar-copy', _minimal_product('collar-copy'))
        img_file = prod_dir / 'images' / 'collar-copy.png'
        img_file.write_bytes(b'\x89PNG\r\n\x1a\n')

        data = _minimal_product('collar-copy')
        data['imagenes'] = [{'archivo': 'collar-copy.png'}]
        (prod_dir / 'data.json').write_text(json.dumps(data), encoding='utf-8')

        call_command('import_catalog_oja', catalog_dir=str(tmp_path))

        dest = media / 'products' / 'images' / 'collar-copy.png'
        assert dest.exists()

    def test_imagen_faltante_no_rompe_import(self, db, tmp_path, settings):
        settings.MEDIA_ROOT = str(tmp_path / 'media')
        col = tmp_path / 'collares-y-pulseras'
        col.mkdir()
        prod_dir = _make_product_dir(col, 'collar-noimg', _minimal_product('collar-noimg'))
        data = _minimal_product('collar-noimg')
        data['imagenes'] = [{'archivo': 'no-existe.png'}]
        (prod_dir / 'data.json').write_text(json.dumps(data), encoding='utf-8')

        call_command('import_catalog_oja', catalog_dir=str(tmp_path))

        assert Product.objects.filter(slug='collar-noimg').exists()
        img = ProductImage.objects.filter(
            product__slug='collar-noimg', order=0
        ).first()
        assert img is not None
        assert img.image == 'products/images/no-existe.png'


# ---------------------------------------------------------------------------
# Pruebas de --dry-run
# ---------------------------------------------------------------------------

class TestImportCatalogOjaDryRun:
    """--dry-run no escribe en BD ni copia archivos."""

    def test_dry_run_no_crea_categorias(self, db, catalog_dir):
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir), dry_run=True)

        assert Category.objects.filter(slug='collares-y-pulseras').count() == 0
        assert Category.objects.filter(slug='ingredientes-rituales').count() == 0

    def test_dry_run_no_crea_productos(self, db, catalog_dir):
        call_command('import_catalog_oja', catalog_dir=str(catalog_dir), dry_run=True)

        assert Product.objects.filter(slug='collar-azul').count() == 0

    def test_dry_run_no_copia_imagenes(self, db, tmp_path, settings):
        media = tmp_path / 'media'
        settings.MEDIA_ROOT = str(media)
        col = tmp_path / 'collares-y-pulseras'
        col.mkdir()
        prod_dir = _make_product_dir(col, 'collar-dry', _minimal_product('collar-dry'))
        (prod_dir / 'images' / 'collar-dry.png').write_bytes(b'\x89PNG\r\n\x1a\n')
        data = _minimal_product('collar-dry')
        data['imagenes'] = [{'archivo': 'collar-dry.png'}]
        (prod_dir / 'data.json').write_text(json.dumps(data), encoding='utf-8')

        call_command('import_catalog_oja', catalog_dir=str(tmp_path), dry_run=True)

        assert not (media / 'products' / 'images' / 'collar-dry.png').exists()


# ---------------------------------------------------------------------------
# Pruebas de --category filter
# ---------------------------------------------------------------------------

class TestImportCatalogOjaFilter:
    """--category importa solo la categoría indicada."""

    def test_category_filter_importa_solo_la_indicada(self, db, catalog_dir):
        call_command(
            'import_catalog_oja',
            catalog_dir=str(catalog_dir),
            category='collares-y-pulseras',
        )

        assert Product.objects.filter(slug='collar-azul').exists()
        assert not Product.objects.filter(slug='aceite-oya').exists()

    def test_category_filter_crea_solo_su_categoria(self, db, catalog_dir):
        call_command(
            'import_catalog_oja',
            catalog_dir=str(catalog_dir),
            category='collares-y-pulseras',
        )

        assert Category.objects.filter(slug='collares-y-pulseras').exists()
        assert not Category.objects.filter(slug='ingredientes-rituales').exists()


# ---------------------------------------------------------------------------
# Prueba de directorio inexistente
# ---------------------------------------------------------------------------

class TestImportCatalogOjaMissingDir:
    """Directorio inexistente termina sin lanzar excepción."""

    def test_directorio_inexistente_sale_sin_excepcion(self, db):
        call_command('import_catalog_oja', catalog_dir='/ruta/que/no/existe/')
        # El command escribe en stderr pero no lanza excepción
        assert Category.objects.count() == 0
