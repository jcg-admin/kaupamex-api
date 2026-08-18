"""Tests — ``stock.warehouse.orderpoint`` (adaptación de Odoo ``stock``).

Cubre la regla de reabastecimiento: sus atributos de clase, la restricción de
unicidad producto+ubicación+empresa, las dos guardas de ``create``/``write``
(dormir sólo reglas manuales; no cambiar de empresa en caliente), los compute
almacenados que ``save()`` dispara, y la pareja
``qty_to_order`` / ``_inverse_qty_to_order`` — el par que la referencia declara
como campo calculado con inverso y que aquí es ``property`` con setter (D-2 del
docstring del módulo portado).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from addons.base.models import ResCompany
from addons.stock.models import (
    StockLocation,
    StockMove,
    StockPicking,
    StockRoute,
    StockWarehouse,
    StockWarehouseOrderpoint,
)
from exceptions import UserError
from orm.environments import set_current_company
from tests.factories.product_factory import make_product

pytestmark = pytest.mark.integration


@pytest.fixture
def company(db):
    """Empresa activa — precondición de todo lo que declara ``company_id``.

    No es ``autouse``: los demás archivos de este directorio no la necesitan y
    activarla para todos cambiaría su contexto.
    """
    empresa = ResCompany.objects.create(code='test_orderpoint', name='Test OP')
    set_current_company(empresa.pk)
    yield empresa
    set_current_company(None)


@pytest.fixture
def warehouse(company):
    """El almacén cuya estantería resuelven ``_compute_location_id`` y su par."""
    # El ``barcode`` va explícito: ``StockLocation`` lleva unicidad
    # ``(barcode, company)`` y dos vacíos en la misma empresa colisionan.
    view = StockLocation.objects.create(
        name='WH', usage=StockLocation.USAGE_VIEW, company=company,
        barcode='OP-VIEW')
    stock = StockLocation.objects.create(
        name='WH/Stock', usage=StockLocation.USAGE_INTERNAL,
        location=view, company=company, barcode='OP-STOCK')
    return StockWarehouse.objects.create(
        name='Main', code='WH', company=company,
        view_location=view, lot_stock=stock)


def _orderpoint(company, wh, **kwargs):
    """Una regla mínima; los compute rellenan almacén, ubicación y máximo.

    El segundo parámetro se llama ``wh`` a propósito: ``warehouse`` es una clave
    legítima de ``kwargs`` (los tests que ejercitan ``_compute_warehouse_id``
    pasan ``warehouse=None``), y con el mismo nombre chocaría.
    """
    kwargs.setdefault('product', make_product(name='Replenished'))
    kwargs.setdefault('company', company)
    kwargs.setdefault('warehouse', wh)
    kwargs.setdefault('location', wh.lot_stock)
    return StockWarehouseOrderpoint.objects.create(**kwargs)


# === atributos de clase de modelo (``odoo19c: stock_orderpoint.py:23-26``) ===


def test_the_class_declares_the_four_orm_attributes_of_the_source():
    """≙ ``_name``/``_description``/``_check_company_auto``/``_order``."""
    assert StockWarehouseOrderpoint._name == 'stock.warehouse.orderpoint'
    assert StockWarehouseOrderpoint._description == 'Minimum Inventory Rule'
    assert StockWarehouseOrderpoint._check_company_auto is True
    assert StockWarehouseOrderpoint._order == 'location_id,company_id,id'


def test_the_table_name_matches_what_the_source_would_derive_from_name():
    """``_table = _name.replace('.', '_')`` (``odoo19c: model_classes.py:266``)."""
    assert StockWarehouseOrderpoint._meta.db_table == 'stock_warehouse_orderpoint'


# === la restricción de unicidad (``_product_location_check``, :101-104) =====


def test_a_second_rule_for_the_same_product_and_location_is_rejected(
        company, warehouse):
    """≙ ``_product_location_check`` — una regla por producto y ubicación."""
    product = make_product(name='Only once')
    _orderpoint(company, warehouse, product=product)
    with pytest.raises(IntegrityError):
        _orderpoint(company, warehouse, product=product)


# === las dos guardas de create/write (:292-306) ==============================


def test_an_auto_rule_can_not_be_snoozed(company, warehouse):
    """≙ la guarda de ``create`` — dormir es sólo para reglas manuales."""
    with pytest.raises(UserError):
        _orderpoint(company, warehouse, trigger='auto',
                    snoozed_until=date(2026, 12, 31))


def test_a_manual_rule_accepts_being_snoozed(company, warehouse):
    """El contrapositivo: la guarda no bloquea la rama que la fuente permite."""
    orderpoint = _orderpoint(company, warehouse, trigger='manual',
                             snoozed_until=date(2026, 12, 31))
    assert orderpoint.snoozed_until == date(2026, 12, 31)


def test_the_company_can_not_be_changed_once_the_rule_exists(company, warehouse):
    """≙ la guarda de ``write`` — se archiva y se crea otra, no se muda."""
    orderpoint = _orderpoint(company, warehouse)
    otra = ResCompany.objects.create(code='other_op', name='Other OP')
    orderpoint.company = otra
    with pytest.raises(UserError):
        orderpoint.save()


# === los compute almacenados que save() dispara =============================


def test_the_maximum_never_stays_below_the_minimum(company, warehouse):
    """≙ ``_compute_product_max_qty`` (``:209-213``)."""
    orderpoint = _orderpoint(company, warehouse, product_min_qty=10.0,
                             product_max_qty=0.0)
    assert orderpoint.product_max_qty == 10.0


def test_an_explicit_maximum_above_the_minimum_survives(company, warehouse):
    """El compute sólo corrige hacia arriba; no pisa un máximo válido."""
    orderpoint = _orderpoint(company, warehouse, product_min_qty=10.0,
                             product_max_qty=40.0)
    assert orderpoint.product_max_qty == 40.0


def test_the_location_is_filled_from_the_warehouse_when_absent(company, warehouse):
    """≙ ``_compute_location_id`` (``:277-285``) — la estantería del almacén."""
    orderpoint = _orderpoint(company, warehouse, location=None)
    assert orderpoint.location == warehouse.lot_stock


def test_the_warehouse_is_filled_from_the_location_when_absent(company, warehouse):
    """≙ ``_compute_warehouse_id`` (``:265-275``) — el almacén sale del lugar."""
    orderpoint = _orderpoint(company, warehouse, warehouse=None)
    assert orderpoint.warehouse == warehouse


def test_the_minimum_above_the_maximum_is_rejected_by_clean(company, warehouse):
    """≙ ``_check_min_max_qty`` (``:255-259``) — corre como ``clean()``."""
    orderpoint = _orderpoint(company, warehouse, product_min_qty=5.0,
                             product_max_qty=20.0)
    orderpoint.product_max_qty = 1.0
    with pytest.raises(ValidationError):
        orderpoint.clean()


# === qty_to_order y su inverso (:390-402) ===================================


def test_the_manual_quantity_wins_over_the_computed_one(company, warehouse):
    """≙ ``_compute_qty_to_order`` — «manual if manual else computed»."""
    orderpoint = _orderpoint(company, warehouse, trigger='manual',
                             qty_to_order_computed=7.0, qty_to_order_manual=3.0)
    assert orderpoint.qty_to_order == 3.0


def test_without_a_manual_quantity_the_computed_one_answers(company, warehouse):
    orderpoint = _orderpoint(company, warehouse,
                             qty_to_order_computed=7.0, qty_to_order_manual=0.0)
    assert orderpoint.qty_to_order == 7.0


def test_assigning_on_an_auto_rule_clears_the_manual_quantity(company, warehouse):
    """≙ ``_inverse_qty_to_order`` rama ``auto`` — la manda el cálculo."""
    orderpoint = _orderpoint(company, warehouse, trigger='auto',
                             qty_to_order_computed=7.0, qty_to_order_manual=3.0)
    orderpoint.qty_to_order = 12.0
    assert orderpoint.qty_to_order_manual == 0


def test_assigning_the_computed_value_on_a_manual_rule_is_not_pinning_it(
        company, warehouse):
    """≙ ``_inverse_qty_to_order`` — asignar lo calculado no es fijar a mano."""
    orderpoint = _orderpoint(company, warehouse, trigger='manual',
                             qty_to_order_computed=7.0, qty_to_order_manual=0.0)
    orderpoint.qty_to_order = 7.0
    assert orderpoint.qty_to_order_manual == 0


def test_assigning_a_different_value_on_a_manual_rule_pins_it(company, warehouse):
    orderpoint = _orderpoint(company, warehouse, trigger='manual',
                             qty_to_order_computed=7.0, qty_to_order_manual=0.0)
    orderpoint.qty_to_order = 11.0
    assert orderpoint.qty_to_order_manual == 11.0


# === los buscadores sin columna (:404-411, :244-249) ========================


def test_the_search_of_qty_to_order_covers_both_branches(company, warehouse):
    """≙ ``_search_qty_to_order`` — manual si la hay, calculada si no."""
    con_manual = _orderpoint(company, warehouse, trigger='manual',
                             qty_to_order_computed=1.0, qty_to_order_manual=5.0)
    sin_manual = _orderpoint(company, warehouse,
                             product=make_product(name='Second'),
                             qty_to_order_computed=5.0, qty_to_order_manual=0.0)
    encontrados = set(StockWarehouseOrderpoint.objects.filter(
        StockWarehouseOrderpoint._search_qty_to_order('=', 5.0),
    ).values_list('pk', flat=True))
    assert encontrados == {con_manual.pk, sin_manual.pk}


def test_the_search_of_the_effective_route_returns_the_matching_rules(
        company, warehouse):
    """≙ ``_search_effective_route_id`` — busca en Python, devuelve por ``id``."""
    ruta = StockRoute.objects.create(name='Buy', company=company)
    con_ruta = _orderpoint(company, warehouse, route=ruta)
    _orderpoint(company, warehouse, product=make_product(name='Routeless'))
    encontrados = set(StockWarehouseOrderpoint.objects.filter(
        StockWarehouseOrderpoint._search_effective_route_id('=', ruta.pk),
    ).values_list('pk', flat=True))
    assert con_ruta.pk in encontrados


# === el horizonte (:804-811) ================================================


def test_the_horizon_comes_from_the_company_of_the_given_rules(company, warehouse):
    """≙ ``get_horizon_days`` — segundo nivel de prioridad de la fuente."""
    company.horizon_days = 9
    company.save(update_fields=['horizon_days'])
    orderpoint = _orderpoint(company, warehouse)
    assert StockWarehouseOrderpoint.get_horizon_days([orderpoint]) == 9


def test_without_rules_the_horizon_falls_back_to_the_active_company(company):
    """≙ el tercer nivel: «the value set on the company of the user»."""
    company.horizon_days = 4
    company.save(update_fields=['horizon_days'])
    assert StockWarehouseOrderpoint.get_horizon_days() == 4


def test_days_to_order_is_zero_as_in_the_source(company, warehouse):
    """≙ ``_compute_days_to_order`` (``:251-253``) — «``self.days_to_order = 0``»."""
    assert _orderpoint(company, warehouse).days_to_order == 0.0


# === la FK inversa: StockMove.orderpoint (odoo19c: stock_move.py:189) =======
#
# La referencia declara ``orderpoint_id = fields.Many2one(
# 'stock.warehouse.orderpoint', 'Original Reordering Rule', index=True)``.
# Aquí el field pierde el sufijo ``_id`` por la convención del árbol.


def test_the_move_declares_the_foreign_key_back_to_the_rule():
    """≙ ``odoo19c: stock_move.py:189`` — el field, su destino y su índice."""
    field = StockMove._meta.get_field('orderpoint')
    assert field.related_model is StockWarehouseOrderpoint
    assert field.db_index is True, 'la fuente lo declara index=True'
    assert field.null is True, 'la fuente no lo declara required'


def test_the_rule_reaches_its_moves_by_the_reverse_accessor(company, warehouse):
    """El ``related_name`` es lo que hace resoluble el dominio de la fuente.

    ``odoo19c: stock_orderpoint.py:645`` busca los movimientos con
    ``Domain('orderpoint_id', 'in', self.ids)``; aquí ese mismo conjunto sale
    del acceso inverso.
    """
    orderpoint = _orderpoint(company, warehouse)
    move = StockMove.objects.create(
        product=orderpoint.product, product_uom_qty=Decimal('3'),
        location=warehouse.lot_stock, location_dest=warehouse.lot_stock,
        orderpoint=orderpoint)
    assert list(orderpoint.stock_moves.all()) == [move]


def test_the_notification_answers_when_the_transfer_came_from_another_warehouse(
        company, warehouse):
    """≙ ``_get_replenishment_order_notification`` con su rama verdadera.

    Hasta que la FK existió, el método se protegía con un guard sobre
    ``_meta.get_fields()`` y devolvía ``False`` siempre — el rodeo que la
    tarea #382 retira.
    """
    other_view = StockLocation.objects.create(
        name='WH2', usage=StockLocation.USAGE_VIEW, company=company,
        barcode='OP2-VIEW')
    other_stock = StockLocation.objects.create(
        name='WH2/Stock', usage=StockLocation.USAGE_INTERNAL,
        location=other_view, company=company, barcode='OP2-STOCK')
    other_wh = StockWarehouse.objects.create(
        name='Second', code='WH2', company=company,
        view_location=other_view, lot_stock=other_stock)
    # El ``save()`` explícito NO es adorno: ``StockLocation.warehouse`` es un
    # compute **almacenado** que sólo corre al guardar la ubicación, así que
    # crear el almacén después la deja apuntando a ``None``. En la fuente el
    # field es ``compute=`` sin ``store=`` y se recalcula al leerlo. Ver
    # :ref:`h-api-667` — el mismo defecto de clase que la tarea #277.
    other_stock.save()
    other_stock.refresh_from_db()

    orderpoint = _orderpoint(company, warehouse)
    picking = StockPicking.objects.create(
        location=other_wh.lot_stock, location_dest=warehouse.lot_stock)
    StockMove.objects.create(
        product=orderpoint.product, product_uom_qty=Decimal('3'),
        location=other_wh.lot_stock, location_dest=warehouse.lot_stock,
        picking=picking, orderpoint=orderpoint)

    notification = orderpoint._get_replenishment_order_notification()
    assert notification is not False
    assert notification['tag'] == 'display_notification'
    assert notification['params']['links'][0]['label'] == picking.name


def test_the_notification_stays_silent_inside_the_same_warehouse(
        company, warehouse):
    """≙ la rama falsa: mismo almacén y sin tránsito no genera aviso."""
    orderpoint = _orderpoint(company, warehouse)
    picking = StockPicking.objects.create(
        location=warehouse.lot_stock, location_dest=warehouse.lot_stock)
    StockMove.objects.create(
        product=orderpoint.product, product_uom_qty=Decimal('3'),
        location=warehouse.lot_stock, location_dest=warehouse.lot_stock,
        picking=picking, orderpoint=orderpoint)
    assert orderpoint._get_replenishment_order_notification() is False
