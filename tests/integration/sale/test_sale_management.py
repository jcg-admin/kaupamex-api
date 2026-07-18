"""Tests — addon ``sale_management`` (sale.order.template).

Plantillas de cotización reutilizables (Odoo sale.order.template +
sale.order.template.line).
"""
from decimal import Decimal

import pytest

from addons.catalogue.models import Category, Product
from addons.sale_management.models import SaleOrderTemplate, SaleOrderTemplateLine

pytestmark = pytest.mark.integration


@pytest.fixture
def producto(db):
    cat = Category.objects.create(name='Cat T', slug='cat-tpl', is_active=True)
    p = Product.objects.create(
        name='Prod T', slug='prod-tpl', sku='TPL-001',
        description='', price=Decimal('100.00'), stock=5,
        is_active=True, is_published=True,
    )
    p.categories.add(cat)
    return p


def test_template_creation_defaults(db):
    t = SaleOrderTemplate.objects.create(name='Plantilla base')
    assert t.active is True
    assert t.sequence == 10
    assert t.prepayment_percent == Decimal('0.00')
    assert str(t) == 'Plantilla base'


def test_template_lines_product_and_section(producto):
    t = SaleOrderTemplate.objects.create(name='Con líneas')
    prod_line = SaleOrderTemplateLine.objects.create(
        template=t, product=producto, product_uom_qty=Decimal('2.00'), sequence=20,
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
