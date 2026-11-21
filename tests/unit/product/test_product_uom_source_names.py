"""``product.uom``: ``product_id`` y ``company_id`` con nombre y default.

≙ ``odoo19c: addons/product/models/product_uom.py:14-16``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-uom-source-names.md``.

*Métrica:* el nombre y la columna de los dos campos, el nombre compuesto y
el default de empresa.
*Ciega a:* ``_compute_display_name`` con ``show_variant_name``, que el
módulo declara no portado.
"""
import pytest

from addons.base.models.res_company import ResCompany
from addons.product.models import ProductProduct, ProductTemplate, ProductUom
from addons.uom.models import Uom
from orm.environments import company_scope

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('name', ['product_id', 'company_id'])
def test_the_field_keeps_the_source_name_and_column(name):
    assert ProductUom._meta.get_field(name).column == name


def _packaging(barcode, **values):
    unit = Uom.objects.create(name='Unidad ' + barcode, relative_factor=1.0)
    template = ProductTemplate.objects.create(name='Plantilla ' + barcode,
                                              uom_id=unit)
    variant = ProductProduct.objects.create(product_tmpl_id=template)
    return ProductUom.objects.create(uom_id=unit, product_id=variant,
                                     barcode=barcode, **values)


def test_the_name_joins_the_barcode_and_the_variant():
    """≙ ``_compute_display_name`` (``odoo19c: product_uom.py:28-32``): el
    código y la variante, sólo con ``show_variant_name``."""
    packaging = _packaging('PU-0001')
    shown = packaging.with_context(show_variant_name=True)
    assert shown.display_name == (
        f'PU-0001 for: {packaging.product_id.display_name}')


def test_without_a_company_the_active_one_is_taken():
    company = ResCompany.objects.create(name='Empresa pu')
    with company_scope(company.pk):
        packaging = _packaging('PU-0002')
    assert packaging.company_id == company
