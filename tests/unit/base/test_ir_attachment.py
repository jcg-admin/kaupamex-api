"""Contrato de ``IrAttachment`` (``ir.attachment``) — portación fiel de Odoo,
iniciativa ``adaptar-familias-odoo-monolito-modular`` (SOL-096, H-BASE-01 C-2).

Verifica:

- importable desde el hogar canónico ``addons.base.models``,
- ``db_table``/``app_label`` fieles a Odoo (``ir_attachment`` / ``base``),
- campos faithful presentes (nombre Odoo, no tipo Odoo exacto — ver
  divergencias documentadas en ``ir_attachment.py``),
- cómputo de ``file_size``/``checksum`` (sha1) al guardar con ``datas``,
  igual que Odoo ``_get_datas_related_values`` (simplificado: FileField, sin
  filestore propio),
- adjuntos ``type='url'`` sin contenido binario,
- vínculo polimórfico ``res_model``/``res_id`` como campos planos (sin FK,
  igual que Odoo — no hay ``GenericForeignKey``),
- ``company`` FK nullable con ``on_delete=SET_NULL`` (Odoo ``company_id``).

Toca DB → django_db.
"""
import hashlib

import pytest
from django.core.files.base import ContentFile

from addons.base.models import IrAttachment
from addons.base.models import ResCompany

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _make_company():
    return ResCompany.objects.create(code='acme-attach', name='Acme Attach')


# --- Importable desde el hogar canónico ------------------------------------

def test_importable_desde_addons_base_models():
    assert IrAttachment.__module__ == 'addons.base.models.ir_attachment'


# --- db_table / app_label fieles a Odoo ------------------------------------

def test_db_table_fiel_a_odoo():
    assert IrAttachment._meta.db_table == 'ir_attachment'
    assert IrAttachment._meta.app_label == 'base'


def test_campos_faithful_presentes():
    field_names = {f.name for f in IrAttachment._meta.get_fields()}
    for expected in (
        'name', 'description', 'res_model', 'res_field', 'res_id',
        'type', 'url', 'public', 'access_token', 'mimetype', 'file_size',
        'checksum', 'store_fname', 'datas', 'company',
    ):
        assert expected in field_names, f'falta el campo Odoo {expected!r}'


# --- Creación con datas: file_size + checksum calculados -------------------

def test_create_con_datas_calcula_file_size_y_checksum():
    contenido = b'hola mundo adjunto'
    attachment = IrAttachment.objects.create(
        name='saludo.txt',
        datas=ContentFile(contenido, name='saludo.txt'),
    )
    attachment.refresh_from_db()

    assert attachment.file_size == len(contenido)
    assert attachment.checksum == hashlib.sha1(contenido).hexdigest()
    assert attachment.type == IrAttachment.TYPE_BINARY
    assert attachment.mimetype  # default aplicado si no se especificó


def test_mimetype_explicito_no_se_sobreescribe():
    attachment = IrAttachment.objects.create(
        name='foto.png',
        datas=ContentFile(b'\x89PNG...', name='foto.png'),
        mimetype='image/png',
    )
    assert attachment.mimetype == 'image/png'


# --- type='url' sin datas ---------------------------------------------------

def test_attachment_tipo_url_sin_datas():
    attachment = IrAttachment.objects.create(
        name='enlace-externo',
        type=IrAttachment.TYPE_URL,
        url='https://example.com/archivo.pdf',
    )
    attachment.refresh_from_db()

    assert attachment.type == 'url'
    assert attachment.url == 'https://example.com/archivo.pdf'
    assert not attachment.datas
    assert attachment.file_size == 0
    assert attachment.checksum == ''


# --- Vínculo polimórfico res_model/res_id (campos planos, no FK) -----------

def test_vinculo_polimorfico_res_model_res_id():
    attachment = IrAttachment.objects.create(
        name='imagen-producto.jpg',
        res_model='catalogue.Product',
        res_id=5,
    )
    attachment.refresh_from_db()

    assert attachment.res_model == 'catalogue.Product'
    assert attachment.res_id == 5

    encontrados = IrAttachment.objects.filter(
        res_model='catalogue.Product', res_id=5,
    )
    assert attachment in encontrados


def test_res_id_nullable_sin_vinculo():
    attachment = IrAttachment.objects.create(name='adjunto-suelto')
    assert attachment.res_model == ''
    assert attachment.res_id is None


# --- company FK nullable (SET_NULL) ----------------------------------------

def test_company_fk_nullable():
    attachment = IrAttachment.objects.create(name='sin-empresa')
    assert attachment.company_id is None


def test_company_fk_set_null_al_borrar_company():
    company = _make_company()
    attachment = IrAttachment.objects.create(
        name='con-empresa', company=company,
    )

    company.delete()
    attachment.refresh_from_db()

    assert attachment.company_id is None


# --- __str__ -----------------------------------------------------------

def test_str_devuelve_name():
    attachment = IrAttachment.objects.create(name='mi-adjunto.txt')
    assert str(attachment) == 'mi-adjunto.txt'
