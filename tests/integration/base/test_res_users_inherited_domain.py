"""Un dominio sobre un campo delegado por ``_inherits``.

≙ ``odoo19c: odoo/orm/domains.py:946-953``: *"resolve inherited fields"*.
Un campo que el modelo hereda por ``_inherits`` se busca como
``(<fk del padre>, 'any', [(campo, op, valor)])``. ``res.users`` delega en
``res.partner`` por ``partner`` (``_inherits = {'res.partner': 'partner'}``),
así que ``('name', 'ilike', x)`` sobre usuarios busca el nombre del partner.
"""

import pytest
from django.apps import apps

from orm.domains import Domain, to_q
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


@pytest.fixture
def users(db):
    jack = UserFactory(login='jack@kaupamex.mx')
    jack.partner.name = 'Jack Oneill'
    jack.partner.save()
    sam = UserFactory(login='sam@kaupamex.mx')
    sam.partner.name = 'Samantha Carter'
    sam.partner.save()
    return jack, sam


def _found(domain):
    Users = apps.get_model('base', 'ResUsers')
    return set(Users._base_manager.filter(to_q(Domain(domain), Users))
               .values_list('pk', flat=True))


def test_a_delegated_field_is_searched_on_the_parent(users):
    jack, _ = users
    assert _found([('name', 'ilike', 'oneill')]) == {jack.pk}


def test_a_delegated_field_negated(users):
    jack, sam = users
    found = _found([('name', 'not ilike', 'oneill')])
    assert sam.pk in found and jack.pk not in found


def test_an_own_field_is_not_delegated(users):
    """``login`` es de ``res.users``: no se reescribe hacia el partner."""
    jack, _ = users
    assert _found([('login', '=', 'jack@kaupamex.mx')]) == {jack.pk}
