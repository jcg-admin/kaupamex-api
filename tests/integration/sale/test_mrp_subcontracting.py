"""Tests — addon ``mrp_subcontracting`` (subcontratación + costo real).

Cubre el ancla de subcontratación: la BoM de tipo ``subcontract`` con sus
subcontratistas, la ubicación de subcontratación (constraint interna), el perfil
del subcontratista, el subcontratista de la orden, y el **costo real**: el
terminado absorbe componentes valuados + el servicio del subcontratista.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from addons.mrp.models import MrpBom, MrpBomLine, MrpProduction
from addons.mrp_subcontracting import services as subc
from addons.mrp_subcontracting.models import (
    BomSubcontractor,
    SubcontractProduction,
    Subcontractor,
    SubcontractingLocation,
)
from addons.stock.models import StockLocation, StockMove
from addons.stock_account import services as valuation
from addons.stock_account.models import ProductCosting
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration

User = get_user_model()
_email_seq = [0]


def _product(price='100.00'):
    return make_product(name='Subc', price=Decimal(price))


def _bom(product, **kwargs):
    return MrpBom.objects.create(
        product_tmpl=product.product_tmpl, product=product, **kwargs)


def _partner(email):
    return User.objects.create_user(login=email, password='x')


def _internal(name='WH/Stock'):
    return StockLocation.objects.create(name=name, usage=StockLocation.USAGE_INTERNAL)


def test_bom_type_subcontract_with_subcontractors(db):
    finished = _product()
    bom = _bom(finished, product_qty=Decimal('1'), type=MrpBom.TYPE_SUBCONTRACT)
    sub_a = _partner('subA@practicayoruba.mx')
    sub_b = _partner('subB@practicayoruba.mx')
    BomSubcontractor.objects.create(bom=bom, subcontractor=sub_a)
    BomSubcontractor.objects.create(bom=bom, subcontractor=sub_b)
    assert bom.type == 'subcontract'
    assert bom.subcontractor_links.count() == 2


def test_subcontracting_location_must_be_internal(db):
    customer = StockLocation.objects.create(
        name='Cust', usage=StockLocation.USAGE_CUSTOMER)
    with pytest.raises(ValidationError):
        SubcontractingLocation.objects.create(location=customer)
    # Una ubicación interna sí puede marcarse como de subcontratación.
    internal = _internal()
    flag = SubcontractingLocation.objects.create(location=internal)
    assert flag.is_subcontracting_location is True


def test_subcontractor_profile_holds_its_location(db):
    partner = _partner('sub@practicayoruba.mx')
    loc = _internal('WH/Subc')
    prof = Subcontractor.objects.create(partner=partner, location=loc)
    assert prof.is_subcontractor is True
    assert prof.location == loc
    assert partner.subcontractor_profile == prof


def test_bom_subcontractor_unique(db):
    bom = _bom(_product(), type=MrpBom.TYPE_SUBCONTRACT)
    sub = _partner('dup@practicayoruba.mx')
    BomSubcontractor.objects.create(bom=bom, subcontractor=sub)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            BomSubcontractor.objects.create(bom=bom, subcontractor=sub)


def test_subcontract_produce_cost_is_components_plus_service(db):
    finished = _product()
    comp = _product()
    ProductCosting.for_product(finished, cost_method=ProductCosting.COST_AVERAGE)
    # BoM de subcontratación: 1 terminado consume 2 componentes.
    bom = _bom(finished, product_qty=Decimal('1'), type=MrpBom.TYPE_SUBCONTRACT)
    MrpBomLine.objects.create(bom=bom, product=comp, product_qty=Decimal('2'), sequence=1)

    subc_loc = _internal('WH/Subcontractor')
    prod_loc = StockLocation.objects.create(
        name='WH/Production', usage=StockLocation.USAGE_PRODUCTION)
    dest = _internal('WH/Stock')

    # Los componentes ya están valuados en la ubicación del subcontratista
    # (enviados). Se reciben ahí a $10 c/u.
    ProductCosting.for_product(comp, cost_method=ProductCosting.COST_AVERAGE)
    vendor = StockLocation.objects.create(name='Vendors', usage=StockLocation.USAGE_SUPPLIER)
    receive = StockMove.objects.create(
        product=comp, product_uom_qty=Decimal('2'), quantity=Decimal('2'),
        location=vendor, location_dest=subc_loc)
    valuation.value_move(receive, unit_cost=Decimal('10.00'))

    mo = MrpProduction.objects.create(product=finished, product_qty=Decimal('2'), bom=bom)
    mo.action_confirm()
    subc.subcontract_generate_moves(mo, subc_loc, prod_loc, dest)
    # Servicio del subcontratista: $30 por la tanda.
    unit_cost = subc.subcontract_produce(mo, service_cost=Decimal('30.00'))

    # 2 terminados × (2 comp × $10) = $40 componentes + $30 servicio = $70.
    # unit_cost = 70 / 2 = 35.00.
    assert unit_cost == Decimal('35.0000')
    assert mo.state == mo.STATE_DONE


def test_subcontract_production_links_subcontractor(db):
    mo = MrpProduction.objects.create(
        product=_product(), product_qty=Decimal('1'),
        bom=_bom(_product(), type=MrpBom.TYPE_SUBCONTRACT))
    sub = _partner('link@practicayoruba.mx')
    SubcontractProduction.objects.create(production=mo, subcontractor=sub)
    assert mo.subcontract.subcontractor == sub
