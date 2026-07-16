"""
Tests — CatalogImportCSVView (UC-CAT-IMPORT)

POST /api/v2/admin/catalogue/import-csv/
Cabecera CSV: name, sku, base_price, category_slug, [description], [image_files]
image_files: filenames separados por ';', pre-staged en MEDIA_ROOT/products/images/

BD: practicayoruba_qa (config.settings.testing)
"""
import csv
import io
from decimal import Decimal
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.modules.catalogue.models import Category, Product, ProductImage

pytestmark = pytest.mark.integration

IMPORT_URL = '/api/v2/admin/products/imports/'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_csv(*rows, extra_headers=None):
    """
    Genera un CSV de catálogo como bytes.
    rows: seq de dicts con keys name/sku/base_price/category_slug/description/image_files
    """
    headers = ['name', 'sku', 'base_price', 'category_slug', 'description', 'image_files']
    if extra_headers:
        headers = extra_headers
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers, extrasaction='ignore')
    writer.writeheader()
    for row in rows:
        writer.writerow({h: row.get(h, '') for h in headers})
    return buf.getvalue().encode('utf-8')


def _upload(admin_client, content, filename='catalog.csv', content_type='text/csv'):
    f = SimpleUploadedFile(filename, content, content_type=content_type)
    return admin_client.post(IMPORT_URL, {'file': f}, format='multipart')


def _row(name='Collar Test', sku='TST-001', price='100.00',
         cat='collares', desc='', images=''):
    return {
        'name': name, 'sku': sku, 'base_price': price,
        'category_slug': cat, 'description': desc, 'image_files': images,
    }


# ---------------------------------------------------------------------------
# T-001: Validaciones de archivo
# ---------------------------------------------------------------------------

class TestFileValidation:

    def test_sin_archivo_retorna_400(self, admin_client, db):
        res = admin_client.post(IMPORT_URL, {}, format='multipart')
        assert res.status_code == 400
        assert res.data['codigo_error'] == 'FILE_REQUIRED'

    def test_extension_invalida_retorna_400(self, admin_client, db):
        f = SimpleUploadedFile('catalog.xlsx', b'data', content_type='text/csv')
        res = admin_client.post(IMPORT_URL, {'file': f}, format='multipart')
        assert res.status_code == 400
        assert res.data['codigo_error'] == 'FILE_TYPE_INVALID'

    def test_sin_autenticacion_retorna_401(self, api_client, db):
        f = SimpleUploadedFile('catalog.csv', b'x', content_type='text/csv')
        res = api_client.post(IMPORT_URL, {'file': f}, format='multipart')
        assert res.status_code == 401

    def test_usuario_no_admin_retorna_403(self, auth_client, db):
        f = SimpleUploadedFile('catalog.csv', b'x', content_type='text/csv')
        res = auth_client.post(IMPORT_URL, {'file': f}, format='multipart')
        assert res.status_code == 403

    def test_archivo_mayor_5mb_retorna_400(self, admin_client, db):
        big = b'x' * (5 * 1024 * 1024 + 1)
        f = SimpleUploadedFile('catalog.csv', big, content_type='text/csv')
        res = admin_client.post(IMPORT_URL, {'file': f}, format='multipart')
        assert res.status_code == 400
        assert res.data['codigo_error'] == 'FILE_TOO_LARGE'


# ---------------------------------------------------------------------------
# T-002: Validaciones de cabecera y filas
# ---------------------------------------------------------------------------

class TestCSVValidation:

    def test_cabecera_faltante_retorna_422(self, admin_client, db):
        content = b'name,sku,base_price\nCollares,TST-001,100.00\n'
        res = _upload(admin_client, content)
        assert res.status_code == 422
        assert res.data['codigo_error'] == 'CSV_INVALID_HEADERS'

    def test_csv_vacio_solo_cabecera_retorna_201(self, admin_client, db):
        content = _make_csv()
        res = _upload(admin_client, content)
        assert res.status_code == 201
        assert res.data['creados'] == 0
        assert res.data['actualizados'] == 0

    def test_precio_invalido_retorna_422(self, admin_client, db):
        content = _make_csv(_row(price='no-es-precio'))
        res = _upload(admin_client, content)
        assert res.status_code == 422
        assert res.data['codigo_error'] == 'CSV_ROW_ERRORS'

    def test_sku_vacio_retorna_422(self, admin_client, db):
        content = _make_csv(_row(sku=''))
        res = _upload(admin_client, content)
        assert res.status_code == 422
        assert res.data['codigo_error'] == 'CSV_ROW_ERRORS'

    def test_encoding_no_utf8_retorna_400(self, admin_client, db):
        content = 'nombre,sku,base_price,category_slug\n'.encode('latin-1')
        content += 'Añejo,TST-001,100.00,cat\n'.encode('latin-1')
        f = SimpleUploadedFile('catalog.csv', content, content_type='text/csv')
        res = admin_client.post(IMPORT_URL, {'file': f}, format='multipart')
        assert res.status_code in (400, 422)


# ---------------------------------------------------------------------------
# T-003: Creación de productos
# ---------------------------------------------------------------------------

class TestProductCreation:

    def test_un_producto_sin_imagen_crea_producto(self, admin_client, db):
        content = _make_csv(_row())
        res = _upload(admin_client, content)
        assert res.status_code == 201
        assert res.data['creados'] == 1
        assert res.data['actualizados'] == 0
        assert Product.objects.filter(sku='TST-001').exists()

    def test_categoria_nueva_se_crea_automaticamente(self, admin_client, db):
        assert not Category.objects.filter(slug='nueva-categoria').exists()
        content = _make_csv(_row(cat='nueva-categoria'))
        res = _upload(admin_client, content)
        assert res.status_code == 201
        assert Category.objects.filter(slug='nueva-categoria').exists()

    def test_precio_decimal_correcto(self, admin_client, db):
        content = _make_csv(_row(price='3835.15'))
        _upload(admin_client, content)
        p = Product.objects.get(sku='TST-001')
        assert p.price == Decimal('3835.15')

    def test_description_vacia_producto_creado(self, admin_client, db):
        content = _make_csv(_row(desc=''))
        res = _upload(admin_client, content)
        assert res.status_code == 201
        p = Product.objects.get(sku='TST-001')
        assert p.description == ''

    def test_multiples_productos_en_una_importacion(self, admin_client, db):
        content = _make_csv(
            _row(name='P1', sku='TST-001', cat='col'),
            _row(name='P2', sku='TST-002', cat='col'),
            _row(name='P3', sku='TST-003', cat='col'),
        )
        res = _upload(admin_client, content)
        assert res.status_code == 201
        assert res.data['creados'] == 3
        assert Product.objects.count() >= 3


# ---------------------------------------------------------------------------
# T-004: Manejo de imágenes
# ---------------------------------------------------------------------------

class TestImageHandling:

    def test_imagen_existente_crea_productimage(self, admin_client, db, settings, tmp_path):
        media_images = tmp_path / 'products' / 'images'
        media_images.mkdir(parents=True)
        (media_images / 'foto.png').write_bytes(b'PNG_DATA')
        settings.MEDIA_ROOT = str(tmp_path)

        content = _make_csv(_row(images='foto.png'))
        res = _upload(admin_client, content)
        assert res.status_code == 201
        p = Product.objects.get(sku='TST-001')
        img = ProductImage.objects.get(product=p)
        assert img.image == 'products/images/foto.png'
        assert img.is_cover is True

    def test_dos_imagenes_primera_es_cover(self, admin_client, db, settings, tmp_path):
        media_images = tmp_path / 'products' / 'images'
        media_images.mkdir(parents=True)
        (media_images / 'a.png').write_bytes(b'A')
        (media_images / 'b.png').write_bytes(b'B')
        settings.MEDIA_ROOT = str(tmp_path)

        content = _make_csv(_row(images='a.png;b.png'))
        _upload(admin_client, content)
        p = Product.objects.get(sku='TST-001')
        imgs = ProductImage.objects.filter(product=p).order_by('order')
        assert imgs[0].is_cover is True
        assert imgs[1].is_cover is False

    def test_imagen_faltante_genera_advertencia_no_error(self, admin_client, db, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        content = _make_csv(_row(images='no-existe.png'))
        res = _upload(admin_client, content)
        assert res.status_code == 201
        assert len(res.data['advertencias']) >= 1
        assert 'no-existe.png' in res.data['advertencias'][0]

    def test_imagen_faltante_igual_crea_productimage(self, admin_client, db, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        content = _make_csv(_row(images='faltante.png'))
        _upload(admin_client, content)
        p = Product.objects.get(sku='TST-001')
        assert ProductImage.objects.filter(product=p).exists()

    def test_sin_imagenes_no_crea_productimage(self, admin_client, db):
        content = _make_csv(_row(images=''))
        _upload(admin_client, content)
        p = Product.objects.get(sku='TST-001')
        assert ProductImage.objects.filter(product=p).count() == 0


# ---------------------------------------------------------------------------
# T-005: Idempotencia
# ---------------------------------------------------------------------------

class TestIdempotencia:

    def test_segunda_importacion_actualiza_no_duplica(self, admin_client, db):
        content = _make_csv(_row())
        _upload(admin_client, content)
        assert Product.objects.filter(sku='TST-001').count() == 1

        res2 = _upload(admin_client, content)
        assert res2.status_code == 201
        assert res2.data['creados'] == 0
        assert res2.data['actualizados'] == 1
        assert Product.objects.filter(sku='TST-001').count() == 1

    def test_segunda_importacion_actualiza_precio(self, admin_client, db):
        content1 = _make_csv(_row(price='100.00'))
        _upload(admin_client, content1)
        content2 = _make_csv(_row(price='200.00'))
        _upload(admin_client, content2)
        p = Product.objects.get(sku='TST-001')
        assert p.price == Decimal('200.00')

    def test_segunda_importacion_no_duplica_imagenes(self, admin_client, db, settings, tmp_path):
        settings.MEDIA_ROOT = str(tmp_path)
        content = _make_csv(_row(images='foto.png'))
        _upload(admin_client, content)
        _upload(admin_client, content)
        p = Product.objects.get(sku='TST-001')
        assert ProductImage.objects.filter(product=p).count() == 1
