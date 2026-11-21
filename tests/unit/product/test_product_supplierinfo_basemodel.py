"""``product.supplierinfo`` como ``BaseModel``, completo.

≙ ``odoo19c: addons/product/models/product_supplierinfo.py``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
product-supplierinfo-basemodel.md``.

*Métrica:* los calculados precalculados al crear por el ORM, el precio con
descuento convertido a la unidad del producto, la plantilla deducida de la
variante en ``create`` y ``write``, el filtro de tarifas y el conteo de
variantes de la plantilla.
*Ciega a:* la plantilla de importación, que es metadata.
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany, ResPartner
from addons.product.models import ProductSupplierinfo
from orm.environments import env
from orm.models import BaseModel

pytestmark = pytest.mark.django_db

SUPPLIERINFO = 'product.supplierinfo'


def _template(name='PSB Plantilla', **vals):
    [template] = env()['product.template'].create([{'name': name, **vals}])
    return template


def _partner(name='PSB Proveedor', **vals):
    return ResPartner.objects.create(name=name, **vals)


def _info(**vals):
    [info] = env()[SUPPLIERINFO].create([{'partner_id': _partner().pk,
                                          **vals}])
    return info


def test_the_tariff_is_a_basemodel():
    assert issubclass(ProductSupplierinfo, BaseModel)


def test_the_template_and_unit_are_precomputed_from_the_variant():
    template = _template()
    info = _info(product_id=template.product_variant_ids.id)
    assert info.product_tmpl_id == template
    assert info.product_uom_id == template.uom_id


def test_writing_a_variant_moves_the_template():
    first = _template('PSB Uno')
    second = _template('PSB Dos')
    info = _info(product_tmpl_id=first.id)
    info.write({'product_id': second.product_variant_ids.id})
    assert info.product_tmpl_id == second


def test_the_discounted_price_is_in_the_product_unit():
    [unit] = env()['uom.uom'].create([{'name': 'PSB Unidad',
                                       'relative_factor': 1.0}])
    [dozen] = env()['uom.uom'].create([{'name': 'PSB Docena',
                                        'relative_factor': 12.0,
                                        'relative_uom_id': unit.id}])
    assert dozen.factor == 12.0
    template = _template(uom_id=unit.id)
    info = _info(product_tmpl_id=template.id, product_uom_id=dozen.id,
                 price=Decimal('120.00'), discount=Decimal('10.00'))
    expected = dozen._compute_price(Decimal('120.00'), unit) * (
        1 - Decimal('10.00') / 100)
    assert info.price_discounted == expected
    assert info.price_discounted != Decimal('108.00')


def test_the_variant_count_comes_from_the_template():
    template = _template()
    info = _info(product_tmpl_id=template.id)
    assert info.product_variant_count == 1 == template.product_variant_count


def test_the_filter_keeps_the_company_and_the_active_vendors():
    own = ResCompany.objects.create(code='psb-a', name='Propia psb')
    other = ResCompany.objects.create(code='psb-b', name='Ajena psb')
    template = _template()
    variant = template.product_variant_ids
    shared = _info(product_tmpl_id=template.id)
    mine = _info(product_tmpl_id=template.id, company_id=own.pk)
    _info(product_tmpl_id=template.id, company_id=other.pk)
    [archived] = env()[SUPPLIERINFO].create([{
        'partner_id': _partner('PSB Archivado', active=False).pk,
        'product_tmpl_id': template.id}])
    kept = template.seller_ids._get_filtered_supplier(own, variant)
    assert set(kept.ids) == {shared.id, mine.id}
    assert archived.id not in kept.ids


def test_the_import_template_is_declared():
    [entry] = env()[SUPPLIERINFO].get_import_templates()
    assert entry['template'] == '/product/static/xls/product_supplierinfo.xls'


def test_assigning_false_clears_a_many2one():
    template = _template()
    info = _info(product_id=template.product_variant_ids.id)
    info.product_id = False
    assert not info.product_id


def test_the_compute_deduces_the_template_without_create():
    template = _template()
    info = env()[SUPPLIERINFO].new({
        'partner_id': _partner().pk,
        'product_id': template.product_variant_ids.id})
    assert info.product_tmpl_id == template


def test_create_sanitizes_an_explicit_empty_template():
    """El campo dado en ``vals`` no se precalcula: sólo ``_sanitize_vals``
    lo deduce de la variante."""
    template = _template()
    info = _info(product_id=template.product_variant_ids.id,
                 product_tmpl_id=False)
    assert info.product_tmpl_id == template
