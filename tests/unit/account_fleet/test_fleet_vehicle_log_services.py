"""``account_fleet`` — el puente que cuelga de ``fleet.vehicle.log.services``.

Portación de ``odoo19c: account_fleet/models/fleet_vehicle_log_services.py``
(addon ``account_fleet``, LGPL-3, ``odoo-tools@622ddc2a``).

Wiring pendiente — ver el docstring de ``test_account_move.py`` (mismo
addon, misma limitación). Los guards (``_guard_amount_immutable_when_billed``,
``_unlink_if_no_linked_bill``) se ejercen llamando a los receptores
DIRECTAMENTE (``receptor(sender=Modelo, instance=obj)``) en vez de vía
``.save()``/``.delete()`` reales — esto prueba la lógica del guard sin tocar
la base, y es válido porque Django conecta el receptor a la señal pero el
receptor sigue siendo una función común, invocable con los mismos
argumentos que la señal le pasaría.
"""
import pytest

from addons.account.models import AccountMove, AccountMoveLine
from addons.account_fleet.models.fleet_vehicle_log_services import (
    _guard_amount_immutable_when_billed,
    _IGNORE_LINKED_BILL_CONSTRAINT,
    _SYNCING_FROM_BILL,
    _sync_service_fields_from_line,
    _unlink_if_no_linked_bill,
    account_move_state,
    apply_account_fleet_extensions,
    get_account_move,
    ignore_linked_bill_constraint,
    sync_amount_from_line,
    sync_vehicle_from_line,
)
from addons.fleet.models import FleetVehicle, FleetVehicleLogServices
from exceptions import UserError

pytestmark = pytest.mark.unit

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


@pytest.fixture
def linked_service(bill_line, vehicle):
    return FleetVehicleLogServices(account_move_line=bill_line, vehicle=vehicle)


@pytest.fixture
def unlinked_service():
    return FleetVehicleLogServices()


# -- campo colgado por apply_account_fleet_extensions() ---------------------


class TestCampoColgado:
    def test_account_move_line_existe_y_es_unico(self):
        campo = FleetVehicleLogServices._meta.get_field('account_move_line')
        assert campo.unique is True
        assert campo.related_model is AccountMoveLine

    def test_related_name_es_vehicle_log_services(self):
        """El accesor inverso en ``AccountMoveLine`` — ≙ ``vehicle_log_
        service_ids`` de la referencia (ver ``account_move.py``)."""
        campo = FleetVehicleLogServices._meta.get_field('account_move_line')
        assert campo.remote_field.get_accessor_name() == 'vehicle_log_services'

    def test_apply_extensions_es_idempotente(self):
        apply_account_fleet_extensions()
        apply_account_fleet_extensions()
        nombres = [f.name for f in FleetVehicleLogServices._meta.get_fields()]
        assert nombres.count('account_move_line') == 1


# -- account_move_state -------------------------------------------------------


class TestAccountMoveState:
    def test_con_linea_vinculada(self, linked_service):
        assert account_move_state(linked_service) == 'posted'
        assert linked_service.account_move_state == 'posted'

    def test_sin_linea_vinculada(self, unlinked_service):
        assert account_move_state(unlinked_service) is None


# -- get_account_move (≙ action_open_account_move) ---------------------------


class TestGetAccountMove:
    def test_con_linea_vinculada_devuelve_el_asiento(self, linked_service, move):
        assert get_account_move(linked_service) is move

    def test_sin_linea_vinculada_devuelve_none(self, unlinked_service):
        assert get_account_move(unlinked_service) is None


# -- sync_vehicle_from_line (≙ _compute_vehicle_id) --------------------------


class TestSyncVehicleFromLine:
    def test_copia_el_vehiculo_de_la_linea(self, bill_line, vehicle):
        servicio = FleetVehicleLogServices(account_move_line=bill_line)
        sync_vehicle_from_line(servicio)
        assert servicio.vehicle is vehicle

    def test_no_vacia_un_vehiculo_ya_seteado_si_la_linea_no_trae_uno(self, move, vehicle):
        """Comentario original de la referencia: *"We avoid emptying the
        vehicle_id as it is a required field"*."""
        linea_sin_vehiculo = AccountMoveLine(
            move=move, name='Servicio genérico', display_type='product')
        servicio = FleetVehicleLogServices(
            account_move_line=linea_sin_vehiculo, vehicle=vehicle)
        sync_vehicle_from_line(servicio)
        assert servicio.vehicle is vehicle

    def test_sin_linea_vinculada_no_hace_nada(self, unlinked_service):
        """``vehicle`` es un campo requerido en ``fleet.FleetVehicleLogServices``
        (``on_delete=CASCADE``, sin ``null=True``): leerlo sin haberlo
        asignado nunca lanza ``RelatedObjectDoesNotExist`` (comportamiento
        estándar de Django para una FK requerida, no un bug de este puerto).
        La Observation correcta de "no hizo nada" es el atributo crudo
        ``vehicle_id``, que sí puede leerse sin tocar la base."""
        sync_vehicle_from_line(unlinked_service)
        assert unlinked_service.vehicle_id is None


# -- sync_amount_from_line (≙ _compute_amount) -------------------------------


class TestSyncAmountFromLine:
    def test_copia_el_debe_de_la_linea(self, bill_line):
        servicio = FleetVehicleLogServices(account_move_line=bill_line)
        sync_amount_from_line(servicio)
        assert servicio.amount == 350

    def test_sin_linea_vinculada_no_hace_nada(self, unlinked_service):
        sync_amount_from_line(unlinked_service)
        assert unlinked_service.amount is None


# -- _guard_amount_immutable_when_billed (≙ _inverse_amount) -----------------


class TestGuardAmountImmutableWhenBilled:
    def test_sin_linea_vinculada_no_hace_nada(self, unlinked_service):
        assert _guard_amount_immutable_when_billed(
            sender=FleetVehicleLogServices, instance=unlinked_service) is None

    def test_creacion_pk_none_no_bloquea(self, linked_service):
        """El compute todavía no corrió — el guardado inicial pasa; el
        ``post_save`` de creación sincroniza justo después."""
        assert linked_service.pk is None
        assert _guard_amount_immutable_when_billed(
            sender=FleetVehicleLogServices, instance=linked_service) is None

    def test_bypass_con_syncing_from_bill_no_bloquea(self, linked_service):
        token = _SYNCING_FROM_BILL.set(True)
        try:
            assert _guard_amount_immutable_when_billed(
                sender=FleetVehicleLogServices, instance=linked_service) is None
        finally:
            _SYNCING_FROM_BILL.reset(token)
        assert _SYNCING_FROM_BILL.get() is False


# -- _unlink_if_no_linked_bill (≙ @api.ondelete) -----------------------------


class TestUnlinkIfNoLinkedBill:
    def test_sin_linea_vinculada_no_bloquea(self, unlinked_service):
        assert _unlink_if_no_linked_bill(
            sender=FleetVehicleLogServices, instance=unlinked_service) is None

    def test_con_linea_vinculada_rechaza_el_borrado(self, linked_service):
        with pytest.raises(UserError):
            _unlink_if_no_linked_bill(
                sender=FleetVehicleLogServices, instance=linked_service)

    def test_ignore_linked_bill_constraint_permite_el_borrado(self, linked_service):
        with ignore_linked_bill_constraint():
            assert _unlink_if_no_linked_bill(
                sender=FleetVehicleLogServices, instance=linked_service) is None
        # El bypass no sobrevive al context manager.
        with pytest.raises(UserError):
            _unlink_if_no_linked_bill(
                sender=FleetVehicleLogServices, instance=linked_service)

    def test_ignore_linked_bill_constraint_restaura_el_flag_aunque_el_cuerpo_falle(self):
        """El ``finally`` del context manager corre incluso si el bloque
        lanza — el bypass nunca queda pegado en ``True``."""
        with pytest.raises(ValueError):
            with ignore_linked_bill_constraint():
                assert _IGNORE_LINKED_BILL_CONSTRAINT.get() is True
                raise ValueError('boom')
        assert _IGNORE_LINKED_BILL_CONSTRAINT.get() is False


# -- _sync_service_fields_from_line — el punto único de sincronización ------


class TestSyncServiceFieldsFromLine:
    def test_sin_linea_vinculada_no_hace_nada_ni_guarda(self, unlinked_service):
        # Si intentara guardar, fallaría contra la base (sin migración
        # pendiente) — que no reviente es la Observation de que no llegó
        # a llamar ``.save()``.
        _sync_service_fields_from_line(unlinked_service)
        assert unlinked_service.amount is None
        assert unlinked_service.vehicle_id is None
