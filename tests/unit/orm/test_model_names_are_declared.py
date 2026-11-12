"""Ningún modelo concreto hereda el ``_name`` de un mixin.

Una clase concreta que hereda de ``MailThread`` (o de otro mixin con
``_name``) sin declarar el suyo toma el del mixin: ``_name`` vale
``'mail.thread'``, ``model_by_name`` no la resuelve por su nombre y la
inyección del log-access (DEC-09) no la alcanza. Lo destapó
``account.analytic.account`` (designs/analytic-account-header.md).

Las filas conocidas van con ``xfail`` estricto y el origen de su cabecera:
al corregir una, su caso pasa y obliga a retirar la marca. Una nueva falla.
"""
import pytest
from django.apps import apps

#: modelo → cabecera de la fuente (``odoo19c``), o por qué no tiene.
KNOWN = {
    'base_automation.BaseAutomation':
        'addons/base_automation/models/base_automation.py',
    'fleet.FleetVehicleModel': 'addons/fleet/models/fleet_vehicle_model.py',
    'fleet.FleetVehicle': 'addons/fleet/models/fleet_vehicle.py',
    'fleet.FleetVehicleLogContract':
        'addons/fleet/models/fleet_vehicle_log_contract.py',
    'fleet.FleetVehicleLogServices':
        'addons/fleet/models/fleet_vehicle_log_services.py',
    'mass_mailing.MailingMailing': 'addons/mass_mailing/models/mailing.py',
    'website.StaticPage': 'propio del L0, sin contraparte en la fuente',
    'stock.ReturnRequest': 'propio del L0, sin contraparte en la fuente',
    'helpdesk.SupportTicket': 'propio del L0, sin contraparte en la fuente',
}


def _concrete_models():
    for model in apps.get_models():
        if model._meta.abstract or model._meta.proxy:
            continue
        if getattr(model, '_name', None) is None:
            continue
        label = model._meta.label
        marks = ()
        if label in KNOWN:
            marks = pytest.mark.xfail(strict=True, reason=(
                f'_name heredado de un mixin; cabecera: {KNOWN[label]}'))
        yield pytest.param(model, id=label, marks=marks)


@pytest.mark.parametrize('model', list(_concrete_models()))
def test_the_model_declares_its_own_name(model):
    assert '_name' in model.__dict__, (
        f'{model._meta.label} hereda _name={model._name!r}')


def test_every_known_offender_still_exists():
    labels = {model._meta.label for model in apps.get_models()}
    assert set(KNOWN) <= labels
