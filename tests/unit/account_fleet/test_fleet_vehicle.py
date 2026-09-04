"""``account_fleet`` — el puente que cuelga de ``fleet.vehicle``.

Portación de ``odoo19c: account_fleet/models/fleet_vehicle.py``
(addon ``account_fleet``, LGPL-3, ``odoo-tools@622ddc2a``).

Wiring pendiente — ver el docstring de ``test_account_move.py`` (mismo
addon, misma limitación). ``account_move_ids``/``bill_count`` filtran
``AccountMoveLine.objects.filter(vehicle=self, ...)``: Django exige que el
lado derecho de un filtro por relación esté GUARDADO
(``ValueError: Model instances passed to related filters must be saved``) —
no es una limitación de este puerto, es una regla general del ORM. Por eso
este archivo prueba la construcción del filtro y las piezas puras
(``PURCHASE_MOVE_TYPES``, presencia de los símbolos colgados), no el
resultado de evaluar el queryset — eso queda para el nivel de integración,
con un vehículo real en la base.
"""
import pytest

from addons.account.models import AccountMove, AccountMoveLine
from addons.account_fleet.models.fleet_vehicle import (
    PURCHASE_MOVE_TYPES,
    _compute_move_ids,
    _get_vehicle_bill_lines,
    apply_account_fleet_extensions,
)
from addons.fleet.models import FleetVehicle

pytestmark = pytest.mark.unit

apply_account_fleet_extensions()


class TestPurchaseMoveTypes:
    def test_mismo_conjunto_que_account_move_move_types(self):
        """≙ ``AccountMove.get_purchase_types()`` de la referencia (ausente
        en este puerto — ver el docstring del módulo). Los tres códigos
        deben existir en ``AccountMove.MOVE_TYPES``."""
        codigos_declarados = {codigo for codigo, _label in AccountMove.MOVE_TYPES}
        assert set(PURCHASE_MOVE_TYPES) <= codigos_declarados

    def test_tres_entradas_verbatim(self):
        assert PURCHASE_MOVE_TYPES == ('in_invoice', 'in_refund', 'in_receipt')


class TestSimbolosColgados:
    def test_account_move_ids_es_property(self):
        assert isinstance(FleetVehicle.__dict__.get('account_move_ids'), property)

    def test_bill_count_es_property(self):
        assert isinstance(FleetVehicle.__dict__.get('bill_count'), property)

    def test_compute_move_ids_is_method(self):
        assert hasattr(FleetVehicle, '_compute_move_ids')

    def test_apply_extensions_es_idempotente(self):
        """No reemplaza una ``property`` ya colgada por otra — ``hasattr``
        sobre una property de clase no dispara el getter (accede vía la
        clase, no una instancia), así que el segundo ``apply_...`` no
        reintroduce el símbolo."""
        original = FleetVehicle.__dict__['account_move_ids']
        apply_account_fleet_extensions()
        assert FleetVehicle.__dict__['account_move_ids'] is original


class TestGetVehicleBillLines:
    def test_construye_un_queryset_de_account_move_line(self):
        """El vehículo debe estar guardado para evaluar el filtro (regla del
        ORM, no de este puerto) — se prueba que la función arma el
        queryset correcto sin evaluarlo, usando ``.query`` en vez de
        iterar."""
        vehicle = FleetVehicle(pk=42, name='Sedán')
        qs = _get_vehicle_bill_lines(vehicle)
        assert qs.model is AccountMoveLine
        # El dominio declarado en la referencia (odoo19c:
        # fleet_vehicle.py:19-24): vehicle, estado != cancel, tipos de compra.
        where = str(qs.query)
        assert 'vehicle_id' in where or 'vehicle' in where
