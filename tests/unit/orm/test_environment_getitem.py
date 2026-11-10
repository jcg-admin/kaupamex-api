"""``env[model_name]`` es el recordset vacío del modelo — ≙
``odoo19c: odoo/orm/environments.py:105-107``::

    def __getitem__(self, model_name: str) -> BaseModel:
        \"\"\" Return an empty recordset from the given model. \"\"\"
        return self.registry[model_name](self, (), ())

Y sobre ese recordset encadenan los métodos de la API de recordset sin
salir del entorno. Un modelo de Django que no deriva de ``BaseModel`` no
tiene recordset y sigue devolviendo su clase (divergencia declarada en
``designs/environment-getitem-recordset.md``, G2).
"""
import pytest

from orm.environments import Environment
from orm.models import BaseModel
from orm.utils import SUPERUSER_ID

pytestmark = pytest.mark.django_db

NAME = 'test_orm.shared.compute'


@pytest.fixture
def env(db):
    with Environment(None, SUPERUSER_ID, {}) as environment:
        yield environment


def test_getitem_is_an_empty_recordset_of_the_model(env):
    records = env[NAME]
    assert isinstance(records, BaseModel)
    assert type(records) is env.registry[NAME]
    assert records._name == NAME
    assert records._ids == ()
    assert not records
    assert records.env is env


def test_the_recordset_api_chains_on_the_empty_recordset(env):
    created = env[NAME].create({'name': '1->2'})
    assert created.env is env and len(created) == 1
    assert env[NAME].browse(created.ids).ids == created.ids
    assert env[NAME].search([('id', '=', created.id)]).ids == created.ids
    assert not env[NAME].new({'name': '3->4'}).id
    assert env[NAME].with_context(lang='en_US').env.context['lang'] == \
        'en_US'
    # ``uid == SUPERUSER_ID`` eleva ``su`` (``environments.py:66-67``):
    # se mide ``sudo()`` y el cambio de usuario por ``with_user``.
    assert env[NAME].sudo().env.su is True
    assert env[NAME].with_user(SUPERUSER_ID).env.uid == SUPERUSER_ID


def test_a_django_model_without_recordset_returns_its_class(env):
    model = env['res.currency.rate']
    assert isinstance(model, type)
    assert not issubclass(model, BaseModel)
