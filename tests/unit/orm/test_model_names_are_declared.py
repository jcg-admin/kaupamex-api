"""Ningún modelo concreto hereda el ``_name`` de un mixin.

Una clase concreta que hereda de ``MailThread`` (o de otro mixin con
``_name``) sin declarar el suyo toma el del mixin: ``_name`` vale
``'mail.thread'``, ``model_by_name`` no la resuelve por su nombre y la
inyección del log-access (DEC-09) no la alcanza. Lo destapó
``account.analytic.account`` (designs/analytic-account-header.md).

Los nueve que lo heredaban declaran ahora el suyo (``REPAIRED``); el
recorrido sigue cubriendo todo modelo concreto, así que uno nuevo falla.
"""
import pytest
from django.apps import apps

from orm.registry import model_by_name

#: Los nueve que heredaban el nombre de un mixin, con la identidad que
#: declaran ahora: la de la fuente, o la derivada de su tabla si son propios.
REPAIRED = {
    'base_automation.BaseAutomation': 'base.automation',
    'fleet.FleetVehicleModel': 'fleet.vehicle.model',
    'fleet.FleetVehicle': 'fleet.vehicle',
    'fleet.FleetVehicleLogContract': 'fleet.vehicle.log.contract',
    'fleet.FleetVehicleLogServices': 'fleet.vehicle.log.services',
    'mass_mailing.MailingMailing': 'mailing.mailing',
    'website.StaticPage': 'settings.static.page',
    'stock.ReturnRequest': 'return.request',
    'helpdesk.SupportTicket': 'support.ticket',
}


def _concrete_models():
    for model in apps.get_models():
        if model._meta.abstract or model._meta.proxy:
            continue
        if getattr(model, '_name', None) is None:
            continue
        yield pytest.param(model, id=model._meta.label)


@pytest.mark.parametrize('model', list(_concrete_models()))
def test_the_model_declares_its_own_name(model):
    assert '_name' in model.__dict__, (
        f'{model._meta.label} hereda _name={model._name!r}')


@pytest.mark.parametrize('label', sorted(REPAIRED))
def test_a_repaired_model_resolves_by_its_name(label):
    model = apps.get_model(label)
    assert model._name == REPAIRED[label]
    assert model_by_name(REPAIRED[label]) is model
    assert model._meta.db_table == REPAIRED[label].replace('.', '_')
