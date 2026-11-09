"""``BaseModel._apply_onchange_methods`` — el despacho de los ``@onchange``.

≙ ``odoo19c: odoo/orm/models.py:6975-6994`` y su consumidor
``addons/web/models/models.py:2155-2193``. Diseño en
``designs/apply-onchange-methods.md`` del Workbench.

Los métodos de ``test_orm.category`` se declaran en la prueba: lo que se mide
es el despacho —registro, selección, invocación y propagación—, que es
código del ORM; el cuerpo del método es sólo su entrada.

*Métrica:* el registro ``new()`` tras el despacho y el ``OrderedSet`` de
avisos.
*Ciega a:* la ruta de ``web`` sobre instancias de Django, que cubre
``tests/unit/web/test_models_onchange.py``.
"""
import pytest
from django.contrib.auth import get_user_model

from api import onchange
from exceptions import UserError
from orm import registry
from orm.environments import env as current_env
from orm.environments import sudo, user_scope
from tools.misc import OrderedSet

pytestmark = pytest.mark.django_db


@onchange('name')
def _onchange_name_color(self):
    self.color = len(self.name or '')


@onchange('name')
def _onchange_name_value(self):
    return {'value': {'dummy': 'desde value', 'id': 99, 'unknown': 1}}


@onchange('color')
def _onchange_color_warning(self):
    return {'warning': {'message': 'color cambiado'}}


@onchange('parent_path')
def _onchange_parent_path_fails(self):
    raise UserError('fallo del onchange')


@onchange('dummy')
def _onchange_dummy_nothing(self):
    return False


_METHODS = {
    '_onchange_name_color': _onchange_name_color,
    '_onchange_name_value': _onchange_name_value,
    '_onchange_color_warning': _onchange_color_warning,
    '_onchange_parent_path_fails': _onchange_parent_path_fails,
    '_onchange_dummy_nothing': _onchange_dummy_nothing,
}


@pytest.fixture
def environment():
    user = get_user_model().objects.create_user(
        login='apply-onchange', password=None, name='u')
    with user_scope(user.pk), sudo():
        yield current_env()


@pytest.fixture
def category(environment, monkeypatch):
    model = environment['test_orm.category']
    model_class = type(model.new({}))
    for name, method in _METHODS.items():
        monkeypatch.setattr(model_class, name, method, raising=False)
    registry.clear_marked_methods()
    yield model
    monkeypatch.undo()
    registry.clear_marked_methods()


def _result():
    return {'warnings': OrderedSet()}


def test_the_discussion_registers_its_three_onchange_fields(environment):
    methods = environment['test_orm.discussion'].new({})._onchange_methods
    assert set(methods) == {'name', 'moderator', 'messages'}


def test_only_the_methods_of_the_changed_field_run(category):
    record = category.new({'name': 'abc'})
    result = _result()
    record._apply_onchange_methods('name', result)
    assert record.color == 3
    assert record.dummy == 'desde value'
    assert not result['warnings']


def test_value_skips_id_and_unknown_keys(category):
    record = category.new({'name': 'abc'})
    record._apply_onchange_methods('name', _result())
    assert not record.id


def test_excluded_methods_are_skipped(category):
    record = category.new({'name': 'abc', 'color': 0})
    record._apply_onchange_methods(
        'name', _result(), excluded_methods={_onchange_name_color})
    assert record.color == 0
    assert record.dummy == 'desde value'


def test_a_warning_gets_the_default_title_and_counts_once(category):
    record = category.new({'name': 'abc'})
    result = _result()
    record._apply_onchange_methods('color', result)
    record._apply_onchange_methods('color', result)
    assert list(result['warnings']) == [('Warning', 'color cambiado', '')]


def test_a_false_result_changes_nothing(category):
    record = category.new({'name': 'abc', 'color': 7})
    result = _result()
    record._apply_onchange_methods('dummy', result)
    assert record.color == 7
    assert not result['warnings']


def test_an_error_of_the_method_propagates(category):
    record = category.new({'name': 'abc'})
    with pytest.raises(UserError, match='fallo del onchange'):
        record._apply_onchange_methods('parent_path', _result())


def test_a_field_without_onchange_runs_nothing(category):
    record = category.new({'name': 'abc', 'color': 7})
    result = _result()
    record._apply_onchange_methods('parent', result)
    assert record.color == 7
    assert not result['warnings']
