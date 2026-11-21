"""``product.document`` como ``BaseModel``, completo.

≙ ``odoo19c: addons/product/models/product_document.py``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-document-basemodel.md``.

*Métrica:* el adjunto que crea, copia y borra el documento por el ORM, la
lectura de sus campos por la delegación y el rechazo de una URL inválida
en el ``onchange``.
*Ciega a:* ``product_document_ids`` de la plantilla y la variante, que el
diseño declara con su sucesor.
"""
import pytest

from addons.base.models.ir_attachment import IrAttachment
from addons.product.models import ProductDocument
from exceptions import ValidationError
from orm.environments import env
from orm.models import BaseModel

pytestmark = pytest.mark.django_db


def _documents(*names, **vals):
    return env()['product.document'].create([
        {'name': name, 'type': 'url', 'url': f'https://example.com/{name}',
         **vals}
        for name in names])


def test_the_document_is_a_basemodel():
    assert issubclass(ProductDocument, BaseModel)


def test_creating_a_document_creates_its_attachment():
    document = _documents('manual-pd')
    assert document.ir_attachment_id
    assert document.name == 'manual-pd'
    assert document.ir_attachment_id.url == 'https://example.com/manual-pd'


def test_unlinking_documents_unlinks_their_attachments():
    documents = _documents('uno-pd', 'dos-pd')
    attachments = [document.ir_attachment_id.id for document in documents]
    documents.unlink()
    assert not IrAttachment.objects.filter(pk__in=attachments).exists()


def test_copying_a_document_copies_its_attachment():
    document = _documents('copia-pd')
    copied = document.copy()
    assert copied.ir_attachment_id != document.ir_attachment_id
    assert copied.name == 'copia-pd'


def test_an_invalid_url_is_refused_on_change():
    document = env()['product.document'].new(
        {'name': 'mala-pd', 'type': 'url', 'url': 'example.com'})
    with pytest.raises(ValidationError):
        document._onchange_url()
