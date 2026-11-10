"""``ir.rule.model_id`` y ``ir.rule.global`` — los campos de la fuente.

≙ ``odoo19c: odoo/addons/base/models/ir_rule.py:24`` (``model_id =
fields.Many2one('ir.model', index=True, required=True, ondelete='cascade')``)
y ``:270-279`` (``global``, almacenado y calculado de los grupos, añadido a
la clase por asignación porque ``global`` es palabra reservada). Los
archivos de datos de seguridad nombran el modelo por ``model_id`` y la regla
de estructuras salariales de ``hr`` escribe ``global``. Diseño:
``designs/module-install-cycle.md``, L4d.
"""
import pytest

from addons.base.models import IrModelData, ResGroups
from addons.base.models.ir_model import IrModel
from addons.base.models.ir_rule import IrRule
from orm.environments import env, sudo
from orm.utils import model_field_registry

pytestmark = pytest.mark.django_db

LABEL = 'base.ResPartnerBank'


@pytest.fixture(autouse=True)
def _as_superuser(db):
    with sudo():
        yield


def _model():
    return IrModel.objects.get(model=LABEL)


def test_model_id_is_a_cascading_foreign_key_to_ir_model():
    field = IrRule._meta.get_field('model_id')
    assert field.related_model is IrModel
    assert field.column == 'model_id'
    assert field.remote_field.on_delete.__name__ == 'CASCADE'
    assert model_field_registry(IrModel)['rule_ids'].field is field


def test_naming_the_model_by_model_id_fills_the_label():
    rule = IrRule.objects.create(name='Por model_id', model_id=_model())
    assert rule.model_name == LABEL


def test_naming_the_model_by_label_fills_model_id():
    rule = IrRule.objects.create(name='Por etiqueta', model_name=LABEL)
    assert rule.model_id == _model()


def test_global_is_stored_and_follows_the_groups():
    rule = IrRule.objects.create(name='Global', model_id=_model())
    assert IrRule.objects.filter(pk=rule.pk, **{'global': True}).exists()
    rule.groups.add(IrModelData.ref('base.group_user'))
    # Un ``QuerySet`` de Django no vuelca los campos pendientes; la búsqueda
    # de la fuente sí (``flush_model`` de los campos del dominio).
    env().flush_all()
    rule.refresh_from_db()
    assert getattr(rule, 'global') is False
    assert not IrRule.objects.filter(pk=rule.pk, **{'global': True}).exists()


def test_the_loader_takes_model_id_and_global():
    [rule] = IrRule._load_records_create([{
        'name': 'Desde datos', 'model_id': _model().pk, 'global': True,
        'domain_force': "[(1, '=', 1)]",
    }])
    assert rule.model_name == LABEL
    assert getattr(rule, 'global') is True
