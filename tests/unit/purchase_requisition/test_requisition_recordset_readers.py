"""Las tarifas de una línea de acuerdo como recordset.

``purchase.requisition.line`` y ``product.supplierinfo`` son ``BaseModel``:
el One2many ``supplier_info_ids`` es un recordset, como en la fuente, y
estos sitios lo borraban o actualizaban con el gestor de Django
(``all().delete()``, ``all().update()``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-reverse-queryset.md``.

≙ ``action_cancel`` y ``action_done``
(``odoo19c: addons/purchase_requisition/models/purchase_requisition.py``),
``write`` (``:231-241``) y ``unlink`` (``:243-246``) de la línea.

*Métrica:* las tarifas que quedan tras cada operación.
*Ciega a:* la creación automática de la tarifa al confirmar, que no cambia.
"""
from decimal import Decimal

import pytest
from django.apps import apps

from addons.base.models import ResCompany, ResPartner
from addons.purchase_requisition.models import PurchaseRequisition
from addons.purchase_requisition.models.purchase_requisition import (
    STATE_CONFIRMED, TYPE_BLANKET_ORDER)
from orm.environments import sudo

pytestmark = pytest.mark.django_db

ProductProduct = apps.get_model('product', 'ProductProduct')
ProductSupplierinfo = apps.get_model('product', 'ProductSupplierinfo')
ProductTemplate = apps.get_model('product', 'ProductTemplate')
PurchaseRequisitionLine = apps.get_model(
    'purchase_requisition', 'PurchaseRequisitionLine')


@pytest.fixture
def line():
    with sudo():
        company = ResCompany.objects.create(code='qrr-a', name='QRR')
        vendor = ResPartner.objects.create(name='QRR Proveedor')
        tmpl = ProductTemplate.objects.create(
            name='QRR Producto', list_price=Decimal('10.00'))
        product = ProductProduct.objects.create(product_tmpl_id=tmpl)
        requisition = PurchaseRequisition.objects.create(
            company=company, vendor=vendor,
            requisition_type=TYPE_BLANKET_ORDER)
        line = PurchaseRequisitionLine.objects.create(
            requisition=requisition, product=product, price_unit=5.0,
            product_qty=1.0)
        ProductSupplierinfo.objects.create(
            partner_id=vendor, product_id=product, product_tmpl_id=tmpl,
            price=5.0, purchase_requisition_line=line)
        requisition.state = STATE_CONFIRMED
        requisition.save()
    return line


def _rates(line):
    return ProductSupplierinfo.objects.filter(
        purchase_requisition_line=line.pk)


def test_cancelling_the_agreement_drops_its_rates(line):
    with sudo():
        PurchaseRequisition.objects.get(pk=line.requisition_id).action_cancel()
    assert not _rates(line).exists()


def test_closing_the_agreement_drops_its_rates(line):
    with sudo():
        PurchaseRequisition.objects.get(pk=line.requisition_id).action_done()
    assert not _rates(line).exists()


def test_a_new_price_reaches_the_rates(line):
    with sudo():
        same = PurchaseRequisitionLine.objects.get(pk=line.pk)
        same.price_unit = 7.5
        same.save()
    assert [r.price for r in _rates(line)] == [7.5]


def test_deleting_a_live_line_drops_its_rates(line):
    with sudo():
        PurchaseRequisitionLine.objects.get(pk=line.pk).delete()
    assert not ProductSupplierinfo.objects.filter(
        product_tmpl_id__name='QRR Producto').exists()
