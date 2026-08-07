"""``account_fleet`` — el puente que cuelga de ``account.move``/``account.move.line``.

Portación de ``odoo19c: account_fleet/models/account_move.py``
(addon ``account_fleet``, LGPL-3, ``odoo-tools@622ddc2a``).

Wiring pendiente (ver ``api: src/addons/account_fleet/__init__.py``, sección
"Wiring pendiente"): este addon NO está en ``INSTALLED_APPS`` todavía, y las
columnas nuevas (``AccountMoveLine.vehicle``,
``FleetVehicleLogServices.account_move_line``) no tienen migración — viven en
apps ajenas que este agente tiene prohibido tocar. Este archivo llama
``apply_account_fleet_extensions()`` explícitamente (idempotente) y usa
únicamente instancias **NO guardadas** (nunca ``.save()`` ni
``.objects.create()``) — mismo criterio que
``tests/unit/account_qr_code_emv/test_res_bank.py``.

Los guards/receptores que SÍ necesitan tocar la base (crear/borrar
``FleetVehicleLogServices`` reales, o recorrer ``line_ids.all()`` de un
``AccountMove`` guardado) se ejercen aquí sólo hasta el punto en que la
Observation deja de necesitar una fila real — la rama "éxito" completa queda
para el nivel de integración, una vez el wiring de arriba exista.
"""
import pytest

from addons.account.models import AccountMove, AccountMoveLine
from addons.account_fleet.models.account_move import (
    VENDOR_BILL_SERVICE_XMLID,
    _compute_need_vehicle,
    _create_fleet_service_bills_on_post,
    _detach_vehicle_services_on_line_saved,
    _prepare_fleet_log_service,
    apply_account_fleet_extensions,
)
from addons.base.models import IrModelData
from addons.fleet.models import FleetVehicle

pytestmark = pytest.mark.unit

# Aplicar la extensión una vez al importar el módulo — mismo efecto que
# ``AccountFleetConfig.ready()``, sin depender de ``INSTALLED_APPS``.
apply_account_fleet_extensions()


# -- fixtures — todo NO guardado (sin tocar la base) ------------------------


@pytest.fixture
def vehicle():
    return FleetVehicle(name='Sedán de reparto')


@pytest.fixture
def move():
    return AccountMove(state='posted', move_type='in_invoice', name='BILL/0001')


@pytest.fixture
def bill_line(move, vehicle):
    return AccountMoveLine(
        move=move, name='Cambio de aceite', vehicle=vehicle,
        display_type='product', debit=350,
    )


# -- campos colgados por apply_account_fleet_extensions() -------------------


class TestCamposColgados:
    def test_defaults_de_una_linea_nueva(self):
        nueva = AccountMoveLine()
        assert nueva.vehicle_id is None
        assert nueva.need_vehicle is False

    def test_need_vehicle_es_nonstored(self):
        """No aparece en ``_meta.get_fields()`` — es la propiedad que
        distingue un campo ``store=False`` de uno con columna real."""
        nombres = {f.name for f in AccountMoveLine._meta.get_fields()}
        assert 'need_vehicle' not in nombres
        assert 'vehicle' in nombres

    def test_apply_extensions_es_idempotente(self):
        """Llamar dos veces no duplica ``vehicle`` en ``_meta`` — ``ready()``
        puede correr más de una vez por proceso (recarga del
        autoreloader)."""
        apply_account_fleet_extensions()
        apply_account_fleet_extensions()
        nombres = [f.name for f in AccountMoveLine._meta.get_fields()]
        assert nombres.count('vehicle') == 1


# -- _compute_need_vehicle ----------------------------------------------------


class TestComputeNeedVehicle:
    def test_siempre_false(self, bill_line):
        assert _compute_need_vehicle(bill_line) is False
        assert bill_line._compute_need_vehicle() is False


# -- _prepare_fleet_log_service ----------------------------------------------


class TestPrepareFleetLogService:
    def test_estructura_completa(self, monkeypatch, bill_line, vehicle, move):
        """``vendor_bill_service`` viene de ``IrModelData.ref`` (toca la
        base) — se mockea para probar el resto de la función en puro
        Python, sin depender del wiring pendiente de la semilla."""
        centinela = object()
        monkeypatch.setattr(
            IrModelData, 'ref',
            lambda xmlid, raise_if_not_found=True: centinela)
        vals = bill_line._prepare_fleet_log_service()
        assert vals == {
            'service_type': centinela,
            'vehicle': vehicle,
            'vendor': move.partner,
            'description': 'Cambio de aceite',
            'account_move_line': bill_line,
        }

    def test_llama_a_ref_con_el_xmlid_correcto(self, monkeypatch, bill_line):
        llamadas = []
        monkeypatch.setattr(
            IrModelData, 'ref',
            lambda xmlid, raise_if_not_found=True: llamadas.append(
                (xmlid, raise_if_not_found)) or None)
        bill_line._prepare_fleet_log_service()
        assert llamadas == [(VENDOR_BILL_SERVICE_XMLID, False)]

    def test_vendor_viene_del_asiento_no_de_la_linea(self, monkeypatch, move, vehicle):
        """Divergencia 1 del docstring del módulo: ``api:
        account/models/account_move_line.py`` no declara ``partner`` propio,
        así que el vendor se resuelve del asiento."""
        monkeypatch.setattr(
            IrModelData, 'ref', lambda xmlid, raise_if_not_found=True: None)
        line = AccountMoveLine(
            move=move, name='Llantas', vehicle=vehicle, display_type='product')
        vals = line._prepare_fleet_log_service()
        assert vals['vendor'] is move.partner


# -- _create_fleet_service_bills_on_post — guards (sin tocar la base) -------


class TestCreateFleetServiceBillsOnPostGuards:
    """Cada caso ejerce una rama de salida temprana — ninguna llega a
    ``instance.line_ids.all()`` (requeriría un ``AccountMove`` guardado)."""

    def test_sin_update_fields_no_hace_nada(self, move):
        # No debe intentar tocar la base — si lo hiciera, el fixture
        # (instancia no guardada) haría fallar la consulta antes de esto.
        assert _create_fleet_service_bills_on_post(
            sender=AccountMove, instance=move, update_fields=None) is None

    def test_update_fields_sin_state_no_hace_nada(self, move):
        assert _create_fleet_service_bills_on_post(
            sender=AccountMove, instance=move,
            update_fields=frozenset({'amount_total'})) is None

    def test_state_no_posted_no_hace_nada(self):
        borrador = AccountMove(state='draft', move_type='in_invoice')
        assert _create_fleet_service_bills_on_post(
            sender=AccountMove, instance=borrador,
            update_fields=frozenset({'state'})) is None

    def test_move_type_distinto_de_in_invoice_no_hace_nada(self):
        nota_credito = AccountMove(state='posted', move_type='in_refund')
        assert _create_fleet_service_bills_on_post(
            sender=AccountMove, instance=nota_credito,
            update_fields=frozenset({'state'})) is None

    def test_sin_tipo_de_servicio_semilla_no_hace_nada(self, monkeypatch, move):
        """≙ ``if not vendor_bill_service: return super()._post(soft)``."""
        monkeypatch.setattr(
            IrModelData, 'ref', lambda xmlid, raise_if_not_found=True: None)
        assert _create_fleet_service_bills_on_post(
            sender=AccountMove, instance=move,
            update_fields=frozenset({'state'})) is None


# -- _detach_vehicle_services_on_line_saved — guards (sin tocar la base) ----


class TestDetachVehicleServicesOnLineSavedGuards:
    def test_creado_no_hace_nada(self, bill_line):
        assert _detach_vehicle_services_on_line_saved(
            sender=AccountMoveLine, instance=bill_line, created=True,
            update_fields=None) is None

    def test_update_fields_sin_vehicle_no_hace_nada(self, bill_line):
        assert _detach_vehicle_services_on_line_saved(
            sender=AccountMoveLine, instance=bill_line, created=False,
            update_fields=frozenset({'debit'})) is None

    def test_vehicle_presente_no_hace_nada(self, bill_line):
        """``bill_line`` tiene vehículo — la limpieza sólo corre cuando se
        vacía."""
        assert _detach_vehicle_services_on_line_saved(
            sender=AccountMoveLine, instance=bill_line, created=False,
            update_fields=None) is None
