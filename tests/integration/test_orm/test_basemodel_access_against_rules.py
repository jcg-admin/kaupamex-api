"""La cadena de acceso del recordset de ``BaseModel`` frente al flujo de
``odoo19c: odoo/orm/models.py:4100-4192``, con ACL concedida y reglas de fila.

Las pruebas por símbolo (``test_contract_models_basemodel_*``) sólo cubren la
elevación y la ACL denegada. Aquí se cualifican las ramas que dependen de
``ir.rule``:

- con ACL, la regla acota: los prohibidos son los que su dominio no devuelve
  (``:4142-4147``), y ``_filtered_access`` devuelve el resto **en el orden de
  ``self``** (``self - result[0]``, ``:4127``);
- un recordset vacío pregunta por el modelo en general (``:4108-4112``);
- la regla se evalúa con ``active_test=False`` (``:4145``): un registro
  archivado que la regla admite no es un prohibido;
- las formas obsoletas siguen el mismo veredicto (``:4161-4192``).
"""
import pytest

from addons.base.models.ir_model import IrModel, IrModelAccess
from addons.base.models.ir_rule import IrRule
from exceptions import AccessError
from orm.environments import Environment
from tests.factories.user_factory import UserFactory

pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def _grant(env, model_name, mode='read'):
    label = env[model_name]._meta.label
    row, _ = IrModel.objects.get_or_create(
        model=label, defaults={'name': model_name})
    IrModelAccess.objects.create(
        name=f'chain {mode} {model_name}', model_id=row,
        **{f'perm_{mode}': True})
    return label


def _rule(label, domain):
    IrRule.objects.create(name=f'chain {domain}', model_name=label,
                          domain_force=domain)


def _plain_user():
    return Environment(None, UserFactory().pk, {})


@pytest.fixture
def three_foos(env):
    return env['test_orm.foo'].create(
        [{'value1': 1}, {'value1': 2}, {'value1': 3}])


def test_a_rule_names_the_forbidden_records(env, three_foos):
    _rule(_grant(env, 'test_orm.foo'), "[('value1', '=', 2)]")
    with _plain_user() as plain:
        records = three_foos.with_env(plain)
        forbidden, make_error = records._check_access('read')
        assert sorted(forbidden.ids) == sorted(
            [three_foos[0].id, three_foos[2].id])
        assert isinstance(make_error(), AccessError)
        assert records.has_access('read') is False
        with pytest.raises(AccessError):
            records.check_access('read')


def test_filtered_access_keeps_the_allowed_in_the_order_of_self(
        env, three_foos):
    _rule(_grant(env, 'test_orm.foo'), "[('value1', '>=', 2)]")
    reversed_ids = list(reversed(three_foos.ids))
    with _plain_user() as plain:
        records = plain['test_orm.foo'].browse(reversed_ids)
        assert records._filtered_access('read').ids == [
            three_foos[2].id, three_foos[1].id]


def test_an_allowed_recordset_passes_every_form(env, three_foos):
    _rule(_grant(env, 'test_orm.foo'), "[('value1', '>', 0)]")
    with _plain_user() as plain:
        records = three_foos.with_env(plain)
        assert records._check_access('read') is None
        assert records.check_access('read') is None
        assert records.has_access('read') is True
        assert records._filtered_access('read') == records


def test_an_empty_recordset_asks_about_the_model(env):
    _grant(env, 'test_orm.foo')
    with _plain_user() as plain:
        empty = plain['test_orm.foo'].browse()
        assert empty.has_access('read') is True
        assert empty.has_access('unlink') is False
        with pytest.raises(AccessError):
            empty.check_access('unlink')


def test_the_rule_ignores_the_archived_filter(env):
    label = _grant(env, 'test_orm.model_active_field')
    _rule(label, "[('name', '=', 'kept')]")
    archived = env['test_orm.model_active_field'].create(
        {'name': 'kept', 'active': False})
    with _plain_user() as plain:
        assert archived.with_env(plain)._check_access('read') is None


def test_the_deprecated_forms_follow_the_rule(env, three_foos):
    _rule(_grant(env, 'test_orm.foo'), "[('value1', '=', 2)]")
    with _plain_user() as plain:
        records = three_foos.with_env(plain)
        with pytest.warns(DeprecationWarning), pytest.raises(AccessError):
            records.check_access_rule('read')
        with pytest.warns(DeprecationWarning):
            assert records._filter_access_rules('read').ids == [
                three_foos[1].id]
        with pytest.warns(DeprecationWarning):
            assert plain['test_orm.foo'].check_access_rights(
                'read', raise_exception=False) is True
