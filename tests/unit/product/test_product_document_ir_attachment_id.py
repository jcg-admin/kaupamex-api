"""``product.document.ir_attachment_id``: el enlace de ``_inherits``.

≙ ``odoo19c: addons/product/models/product_document.py:11-16``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-document-ir-attachment-id.md``.

*Métrica:* el nombre y la columna del campo, la delegación en el adjunto,
el borrado del adjunto con su documento y la guarda de ``clean``.
*Ciega a:* los campos del adjunto que el puerto no delega.
"""
import pytest

from addons.base.models.ir_attachment import IrAttachment
from addons.product.models import ProductDocument

pytestmark = pytest.mark.django_db


def _attachment(name):
    return IrAttachment.objects.create(
        name=name, mimetype='application/pdf', type='url',
        url='https://ejemplo.test/' + name, res_model='product.template',
        res_id=0)


def test_the_link_keeps_the_source_name_and_column():
    field = ProductDocument._meta.get_field('ir_attachment_id')
    assert field.column == 'ir_attachment_id'


def test_the_document_delegates_to_its_attachment():
    document = ProductDocument.objects.create(
        ir_attachment_id=_attachment('ficha.pdf'))
    assert (document.name, document.type) == ('ficha.pdf', 'url')


def test_deleting_the_document_deletes_its_attachment():
    attachment = _attachment('manual.pdf')
    ProductDocument.objects.create(ir_attachment_id=attachment).delete()
    assert not IrAttachment.objects.filter(pk=attachment.pk).exists()


def test_clean_without_an_attachment_does_not_raise():
    ProductDocument().clean()
