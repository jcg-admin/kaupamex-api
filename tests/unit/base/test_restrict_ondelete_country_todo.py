"""Estados, ciudades y pasos de acción con ``ondelete='restrict'``.

≙ ``odoo19c: odoo/addons/base/models/res_country.py:204``,
``addons/base_address_extended/models/res_city.py:14`` y
``odoo/addons/base/models/ir_actions.py:1357``: Many2one obligatorios sin
``ondelete``, cuyo defecto es ``restrict`` (``odoo/orm/
fields_relational.py:274-282``). Diseño: ``scripts/workbench/
orm-continuation-plan-20261103T095630/designs/
country-and-todo-restrict-ondelete.md``.

Cada caso deja al padre protegido sólo por la fila del campo medido.
"""
import pytest
from django.db.models import ProtectedError

from addons.base.models import ResCountry, ResCountryState
from addons.base.models.ir_actions import IrActionsActions, IrActionsTodo
from addons.base_address_extended.models import ResCity

pytestmark = pytest.mark.django_db


def _refuses_and_keeps(parent, child):
    with pytest.raises(ProtectedError):
        type(parent).objects.filter(pk=parent.pk).delete()
    assert type(child).objects.filter(pk=child.pk).exists()


def test_deleting_a_country_with_a_state_is_refused():
    country = ResCountry.objects.create(code='XS', name='Con estado')
    state = ResCountryState.objects.create(country=country, code='S1',
                                           name='Estado')
    _refuses_and_keeps(country, state)


def test_deleting_a_country_with_a_city_is_refused():
    country = ResCountry.objects.create(code='XC', name='Con ciudad')
    city = ResCity.objects.create(name='Ciudad', country_id=country)
    _refuses_and_keeps(country, city)


def test_deleting_an_action_with_a_wizard_step_is_refused():
    action = IrActionsActions.objects.create(
        name='probe', type='ir.actions.actions')
    wizard_step = IrActionsTodo.objects.create(action=action)
    _refuses_and_keeps(action, wizard_step)


def test_a_country_without_dependents_can_be_deleted():
    country = ResCountry.objects.create(code='XZ', name='Sola')
    ResCountry.objects.filter(pk=country.pk).delete()
    assert not ResCountry.objects.filter(pk=country.pk).exists()
