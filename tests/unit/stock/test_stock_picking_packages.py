"""Contrato del grupo «Paquetes» de ``stock.picking`` — tarea #521 (continuación).

Fiel a ``odoo19c: addons/stock/models/stock_picking.py`` (``odoo-tools@622ddc2a``,
LGPL-3): los 17 símbolos que quedaron bloqueados en el pase anterior sólo por
aislamiento de write-set (``stock_package.py`` no era escribible). Cada caso
cita la línea de la referencia que fija la regla:

- ``packages_count`` / ``_compute_packages_count`` (``:643``, ``:944-962``)
- ``package_history_ids`` (``:644``, reverso del M2M de
  ``stock_package_history.py``)
- ``show_check_availability`` (``:645-647``, ``:964-980``)
- ``show_allocation`` + ``_get_show_allocation`` (``:648-650``, ``:982-988``,
  ``:1056-1077``)
- ``_check_move_lines_map_quant_package`` (``:1293-1296``)
- ``_get_entire_pack_location_dest`` (``:1298-1302``)
- ``_is_single_transfer`` (``:1304-1306``)
- ``_check_entire_pack`` (``:1308-1324``)
- ``action_put_in_pack`` (``:1761-1766``)
- ``action_add_entire_packs`` (``:1904-1917``)
- ``action_see_packages`` (``:1927-1942``)
- ``action_see_package_histories`` (``:1944-1957``)
- ``_prepare_entire_pack_move_line_vals`` (``:2129-2149``)
"""
from decimal import Decimal

import pytest

from addons.base.models import ResCompany
from addons.product.models import ProductProduct, ProductTemplate
from addons.uom.models.uom_uom import Uom
from addons.stock.models import (
    StockLocation,
    StockMove,
    StockMoveLine,
    StockPackage,
    StockPackageHistory,
    StockPackageType,
    StockPicking,
    StockPickingType,
    StockQuant,
    StockWarehouse,
)

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture
def company(db):
    return ResCompany.objects.create(name='Kaupamex', code='kaupamex_test_521p')


@pytest.fixture
def source(db):
    return StockLocation.objects.create(name='Stock 521P', usage='internal')


@pytest.fixture
def destination(db):
    return StockLocation.objects.create(name='Customers 521P', usage='customer')


@pytest.fixture
def uom(db):
    # La unidad NO se siembra sola: sin ella ``product_tmpl.uom`` es ``None`` y
    # todo compute que convierta cantidades queda mudo (``show_check_availability``
    # lo lee para comparar contra cero).
    return Uom.objects.create(name='Unidad 521P')


@pytest.fixture
def variant(db, uom):
    # ``is_storable=True`` explícito: el default del campo extendido es False
    # (``addons/stock/models/product.py``) y los filtros del grupo lo leen.
    tmpl = ProductTemplate.objects.create(
        name='Camisa 521P', list_price=Decimal('100.00'), is_storable=True,
        uom=uom)
    return ProductProduct.objects.create(product_tmpl=tmpl, default_code='CAM-521P')


@pytest.fixture
def picking_type(db, company):
    return StockPickingType.objects.create(
        name='Entrega 521P', code='outgoing', sequence_code='OUT521P',
        company=company)


@pytest.fixture
def picking(db, company, source, destination, picking_type):
    return StockPicking.objects.create(
        name='OUT/521P', company=company, location=source,
        location_dest=destination, picking_type=picking_type,
        state=StockPicking.STATE_ASSIGNED)


def _line(picking, variant, source, destination, company, **extra):
    values = dict(
        picking=picking, product=variant, location=source,
        location_dest=destination, company=company,
        quantity=Decimal('5'), state='assigned')
    values.update(extra)
    return StockMoveLine.objects.create(**values)


def _package_with_quant(variant, source, qty='5', name='PACK-521P'):
    package = StockPackage.objects.create(name=name)
    quant = StockQuant.objects.create(
        product=variant, location=source, package=package,
        quantity=Decimal(qty))
    return package, quant


class TestIsSingleTransfer:
    def test_an_instance_is_always_a_single_transfer(self, picking):
        # odoo19c :1304-1306 — ``len(self) == 1`` sobre el recordset; una
        # instancia Django es siempre un solo registro.
        assert picking._is_single_transfer() is True


class TestGetEntirePackLocationDest:
    def test_single_destination_returns_its_id(
            self, picking, variant, source, destination, company):
        # odoo19c :1298-1302
        first = _line(picking, variant, source, destination, company)
        second = _line(picking, variant, source, destination, company)
        assert picking._get_entire_pack_location_dest(
            [first, second]) == destination.pk

    def test_multiple_destinations_return_false(
            self, picking, variant, source, destination, company):
        other = StockLocation.objects.create(name='Otra 521P', usage='internal')
        first = _line(picking, variant, source, destination, company)
        second = _line(picking, variant, source, other, company)
        assert picking._get_entire_pack_location_dest([first, second]) is False

    def test_without_lines_returns_false(self, picking):
        assert picking._get_entire_pack_location_dest([]) is False


class TestCheckMoveLinesMapQuantPackage:
    def test_lines_covering_the_package_content_pass(
            self, picking, variant, source, destination, company):
        # odoo19c :1293-1296 + stock_package.py :414-433 — dos sentidos:
        # que no falte y que no sobre.
        package, _quant = _package_with_quant(variant, source, qty='5')
        _line(picking, variant, source, destination, company, package=package)
        assert picking._check_move_lines_map_quant_package(package) is True

    def test_partial_lines_fail(
            self, picking, variant, source, destination, company):
        package, _quant = _package_with_quant(variant, source, qty='5')
        _line(picking, variant, source, destination, company,
              package=package, quantity=Decimal('2'))
        assert picking._check_move_lines_map_quant_package(package) is False


class TestCheckEntirePack:
    def test_entire_package_marks_its_lines(
            self, picking, variant, source, destination, company):
        # odoo19c :1308-1324 — la línea sin destino hereda el paquete como
        # ``result_package`` y se marca ``is_entire_pack``.
        package, _quant = _package_with_quant(variant, source, qty='5')
        line = _line(picking, variant, source, destination, company,
                     package=package)
        picking._check_entire_pack()
        line.refresh_from_db()
        assert line.result_package_id == package.pk
        assert line.is_entire_pack is True

    def test_reusable_package_is_not_assigned(
            self, picking, variant, source, destination, company):
        # odoo19c :1319 — ``package_use != 'reusable'`` es la condición de
        # escritura: un contenedor reutilizable se vacía y vuelve.
        package_type = StockPackageType.objects.create(
            name='Reusable 521P', package_use='reusable')
        package, _quant = _package_with_quant(variant, source, qty='5')
        package.package_type = package_type
        package.save(update_fields=['package_type'])
        line = _line(picking, variant, source, destination, company,
                     package=package)
        picking._check_entire_pack()
        line.refresh_from_db()
        assert line.result_package_id is None
        assert line.is_entire_pack is False

    def test_partial_package_is_not_marked(
            self, picking, variant, source, destination, company):
        package, _quant = _package_with_quant(variant, source, qty='5')
        line = _line(picking, variant, source, destination, company,
                     package=package, quantity=Decimal('2'))
        picking._check_entire_pack()
        line.refresh_from_db()
        assert line.result_package_id is None


class TestPrepareEntirePackMoveLineVals:
    def test_one_line_per_contained_quant(
            self, picking, variant, source):
        # odoo19c :2129-2149 — una línea por quant, con paquete de origen y
        # destino iguales y ``is_entire_pack``.
        package, quant = _package_with_quant(variant, source, qty='3')
        vals = picking._prepare_entire_pack_move_line_vals(
            StockPackage.objects.filter(pk=package.pk))
        assert len(vals) == 1
        entry = vals[0]
        assert entry['product'] == variant
        assert entry['package'] == package
        assert entry['result_package'] == package
        assert entry['is_entire_pack'] is True
        assert entry['quantity'] == quant.quantity
        assert entry['location'] == source
        assert entry['location_dest'] == picking.location_dest
        # Divergencia declarada: la fuente escribe ``'company_id': self.id``
        # (odoo19c :2143) — aquí la empresa es la del albarán.
        assert entry['company'] == picking.company


class TestActionAddEntirePacks:
    def test_creates_lines_from_the_package_quants(
            self, picking, variant, source):
        # odoo19c :1904-1917
        package, _quant = _package_with_quant(variant, source, qty='4')
        assert picking.action_add_entire_packs([package.pk]) is True
        lines = list(picking.move_line_ids.all())
        assert len(lines) == 1
        assert lines[0].package_id == package.pk
        assert lines[0].result_package_id == package.pk
        assert lines[0].is_entire_pack is True

    def test_replaces_lines_that_already_pulled_from_the_package(
            self, picking, variant, source, destination, company):
        # odoo19c :1909-1910 — las líneas que ya tomaban parte del paquete se
        # borran: ahora va entero.
        package, _quant = _package_with_quant(variant, source, qty='4')
        partial = _line(picking, variant, source, destination, company,
                        package=package, quantity=Decimal('1'))
        picking.action_add_entire_packs([package.pk])
        assert not picking.move_line_ids.filter(pk=partial.pk).exists()
        assert picking.move_line_ids.count() == 1

    def test_done_picking_returns_false(self, picking, variant, source):
        package, _quant = _package_with_quant(variant, source)
        picking.state = StockPicking.STATE_DONE
        picking.save(update_fields=['state', 'updated_at'])
        assert picking.action_add_entire_packs([package.pk]) is False


class TestActionPutInPack:
    def test_done_picking_returns_none(self, picking):
        # odoo19c :1765 — sólo delega con el albarán sin terminar/cancelar.
        picking.state = StockPicking.STATE_DONE
        picking.save(update_fields=['state', 'updated_at'])
        assert picking.action_put_in_pack() is None

    def test_delegates_to_the_move_lines(
            self, picking, variant, source, destination, company):
        # odoo19c :1766 → stock_move_line.py :1316-1338 — la línea suelta
        # termina dentro de un paquete nuevo.
        line = _line(picking, variant, source, destination, company,
                     picked=True)
        result = picking.action_put_in_pack(package_name='PACK-DEL-521P')
        line.refresh_from_db()
        assert line.result_package_id is not None
        assert line.result_package.name == 'PACK-DEL-521P'
        assert result is not None


class TestPackagesCount:
    def test_ongoing_picking_counts_live_packages(
            self, picking, variant, source, destination, company):
        # odoo19c :944-962, rama no-done — paquetes cuyo ``picking_ids``
        # incluye al albarán (``_search_picking_ids``).
        package, _quant = _package_with_quant(variant, source)
        _line(picking, variant, source, destination, company,
              result_package=package)
        assert picking.packages_count == 1

    def test_done_picking_counts_histories(
            self, picking, variant, source, company):
        # odoo19c :959-960, rama done — cuenta ``stock.package.history``.
        package, _quant = _package_with_quant(variant, source)
        history = StockPackageHistory.objects.create(
            company=company, package=package, package_name=package.name)
        history.picking_ids.add(picking)
        picking.state = StockPicking.STATE_DONE
        picking.save(update_fields=['state', 'updated_at'])
        assert picking.packages_count == 1

    def test_package_history_ids_is_the_m2m_reverse(
            self, picking, variant, source, company):
        # odoo19c :644 — el M2M vive declarado en stock_package_history.py
        # con ``related_name='package_history_ids'``.
        package, _quant = _package_with_quant(variant, source)
        history = StockPackageHistory.objects.create(
            company=company, package=package, package_name=package.name)
        history.picking_ids.add(picking)
        assert list(picking.package_history_ids.all()) == [history]


class TestShowCheckAvailability:
    def _move(self, picking, variant, source, destination, company, **extra):
        values = dict(
            picking=picking, product=variant, location=source,
            location_dest=destination, company=company,
            product_uom=variant.product_tmpl.uom,
            product_uom_qty=Decimal('5'), state='confirmed')
        values.update(extra)
        return StockMove.objects.create(**values)

    def test_pending_demand_shows_the_button(
            self, picking, variant, source, destination, company):
        # odoo19c :964-980 — confirmado + demanda sin cubrir + movimiento
        # pendiente de cantidad no nula.
        picking.state = StockPicking.STATE_CONFIRMED
        picking.save(update_fields=['state', 'updated_at'])
        self._move(picking, variant, source, destination, company)
        assert picking.show_check_availability is True

    def test_draft_picking_hides_the_button(
            self, picking, variant, source, destination, company):
        picking.state = StockPicking.STATE_DRAFT
        picking.save(update_fields=['state', 'updated_at'])
        self._move(picking, variant, source, destination, company)
        assert picking.show_check_availability is False

    def test_covered_demand_hides_the_button(
            self, picking, variant, source, destination, company):
        # odoo19c :972-974 — ``m.picked or product_uom_qty == quantity``.
        picking.state = StockPicking.STATE_CONFIRMED
        picking.save(update_fields=['state', 'updated_at'])
        self._move(picking, variant, source, destination, company,
                   quantity=Decimal('5'))
        assert picking.show_check_availability is False


class TestShowAllocation:
    def test_outgoing_type_never_shows_allocation(self, picking):
        # odoo19c :1060-1061 — saliente → False, sin mirar nada más.
        assert picking.show_allocation is False

    def test_incoming_with_a_competing_move_shows_allocation(
            self, company, source, destination, variant):
        # odoo19c :1062-1077 — otro albarán espera el mismo producto dentro
        # del almacén del tipo de operación.
        view = StockLocation.objects.create(name='WH-521P', usage='view')
        stock = StockLocation.objects.create(
            name='WH-521P/Stock', usage='internal', location=view)
        warehouse = StockWarehouse.objects.create(
            name='WH 521P', code='W521P', company=company,
            view_location=view, lot_stock=stock)
        picking_type_in = StockPickingType.objects.create(
            name='Recepción 521P', code='incoming', sequence_code='IN521P',
            company=company, warehouse=warehouse)
        reception = StockPicking.objects.create(
            name='IN/521P', company=company, location=source,
            location_dest=stock, picking_type=picking_type_in,
            state=StockPicking.STATE_ASSIGNED)
        StockMove.objects.create(
            picking=reception, product=variant, location=source,
            location_dest=stock, company=company,
            product_uom=variant.product_tmpl.uom,
            product_uom_qty=Decimal('5'), state='assigned')
        # El movimiento que espera, en OTRO albarán, dentro del almacén.
        waiting = StockPicking.objects.create(
            name='OUT/521P-2', company=company, location=stock,
            location_dest=destination, state=StockPicking.STATE_CONFIRMED)
        StockMove.objects.create(
            picking=waiting, product=variant, location=stock,
            location_dest=destination, company=company,
            product_uom=variant.product_tmpl.uom,
            product_uom_qty=Decimal('3'), state='confirmed')
        assert reception.show_allocation is True

    def test_incoming_without_competing_moves_hides_allocation(
            self, company, source, variant):
        view = StockLocation.objects.create(name='WH-521Q', usage='view')
        stock = StockLocation.objects.create(
            name='WH-521Q/Stock', usage='internal', location=view)
        warehouse = StockWarehouse.objects.create(
            name='WH 521Q', code='W521Q', company=company,
            view_location=view, lot_stock=stock)
        picking_type_in = StockPickingType.objects.create(
            name='Recepción 521Q', code='incoming', sequence_code='IN521Q',
            company=company, warehouse=warehouse)
        reception = StockPicking.objects.create(
            name='IN/521Q', company=company, location=source,
            location_dest=stock, picking_type=picking_type_in,
            state=StockPicking.STATE_ASSIGNED)
        StockMove.objects.create(
            picking=reception, product=variant, location=source,
            location_dest=stock, company=company,
            product_uom=variant.product_tmpl.uom,
            product_uom_qty=Decimal('5'), state='assigned')
        assert reception.show_allocation is False


class TestSeePackagesActions:
    def test_action_see_packages_contract(self, picking):
        # odoo19c :1927-1942 — dominio por picking_ids y contexto con
        # ``can_add_entire_packs`` según el código del tipo.
        action = picking.action_see_packages()
        assert action['res_model'] == 'stock.package'
        assert action['domain'] == [('picking_ids', 'in', [picking.pk])]
        assert action['context']['can_add_entire_packs'] is True
        assert action['context']['picking_ids'] == [picking.pk]

    def test_action_see_package_histories_contract(self, picking):
        # odoo19c :1944-1957
        action = picking.action_see_package_histories()
        assert action['res_model'] == 'stock.package.history'
        assert action['domain'] == [('picking_ids', '=', picking.pk)]
        assert action['context'] == {'search_default_main_packages': 1}

