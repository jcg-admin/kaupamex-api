"""Tests — addon ``sale_management`` (sale.order.template).

Plantillas de cotización reutilizables (Odoo sale.order.template +
sale.order.template.line).
"""
from decimal import Decimal

import pytest

from addons.sale_management.models import SaleOrderTemplate, SaleOrderTemplateLine
from tests.factories.product_factory import make_category, make_product

pytestmark = pytest.mark.integration


@pytest.fixture
def producto(db):
    cat = make_category(name='Cat T')
    return make_product(name='Prod T', price=Decimal('100.00'), stock=5, categ=cat)


def test_template_creation_defaults(db):
    t = SaleOrderTemplate.objects.create(name='Plantilla base')
    assert t.active is True
    assert t.sequence == 10
    assert t.prepayment_percent == Decimal('0.00')
    assert str(t) == 'Plantilla base'


def test_template_lines_product_and_section(producto):
    t = SaleOrderTemplate.objects.create(name='Con líneas')
    prod_line = SaleOrderTemplateLine.objects.create(
        template=t, product_id=producto, product_uom_qty=Decimal('2.00'), sequence=20,
    )
    section = SaleOrderTemplateLine.objects.create(
        template=t, name='Servicios', display_type=SaleOrderTemplateLine.DISPLAY_SECTION,
        sequence=10,
    )
    # _order = template, sequence → sección (10) antes que producto (20)
    assert list(t.template_line.all()) == [section, prod_line]
    assert prod_line.display_type == SaleOrderTemplateLine.DISPLAY_PRODUCT
    assert section.product_id is None


def test_template_ordering(db):
    b = SaleOrderTemplate.objects.create(name='B', sequence=20)
    a = SaleOrderTemplate.objects.create(name='A', sequence=10)
    assert list(SaleOrderTemplate.objects.all()) == [a, b]
