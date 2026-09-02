"""``base_automation`` — los tres CRUD de la fuente y los cinco de la acción.

Cubre lo que el pase de la tarea #281 portó:

- ``BaseAutomation.create``/``write``/``unlink``
  (``odoo19c: base_automation/models/base_automation.py:491-521``);
- los cinco que ``ir_actions_server.py`` cuelga sobre ``ir.actions.server``
  (``odoo19c: base_automation/models/ir_actions_server.py:20-62``) y el valor
  que su ``selection_add`` añade a ``usage``.
"""
import pytest

from addons.base.models import IrActionsServer, IrModel
from addons.base_automation.models.base_automation import (
    BaseAutomation, BaseAutomationAction)
from addons.base_automation.models.ir_actions_server import (
    USAGE_BASE_AUTOMATION, _automation_of)

pytestmark = pytest.mark.django_db


@pytest.fixture
def partner_model():
    """Un ``ir.model`` reflejado sobre el que colgar la regla."""
    return IrModel.objects.filter(model='base.ResPartner').first() or \
        IrModel.objects.create(model='base.ResPartner', name='Contacto')


@pytest.fixture
def rule(partner_model):
    return BaseAutomation.objects.create(
        name='Regla de prueba', model_id=partner_model, trigger='on_create')


class TestCreate:
    """≙ ``create`` (``:491-498``) — la puerta que la fuente vigila."""

    def test_it_accepts_a_list_and_returns_the_rules(self, partner_model):
        rules = BaseAutomation.create([
            {'name': 'Una', 'model_id': partner_model, 'trigger': 'on_create'},
            {'name': 'Otra', 'model_id': partner_model, 'trigger': 'on_write'},
        ])
        assert [rule.name for rule in rules] == ['Una', 'Otra']
        assert all(rule.pk is not None for rule in rules)

    def test_a_bare_dict_is_accepted_like_model_create_multi(self, partner_model):
        """La fuente lo declara ``@api.model_create_multi``: acepta un dict."""
        rules = BaseAutomation.create(
            {'name': 'Sola', 'model_id': partner_model, 'trigger': 'on_create'})
        assert len(rules) == 1
        assert rules[0].name == 'Sola'

    def test_the_created_rule_syncs_its_model_name(self, partner_model):
        """La cadena derivada corre: ``save()`` sincroniza ``model_name``."""
        rules = BaseAutomation.create(
            {'name': 'Con nombre', 'model_id': partner_model,
             'trigger': 'on_create'})
        assert rules[0].model_name == partner_model.model


class TestWrite:
    """≙ ``write`` (``:500-511``) — y la asimetría crítico/rango."""

    def test_it_sets_the_values_and_persists_them(self, rule):
        rule.write(name='Renombrada')
        assert BaseAutomation.objects.get(pk=rule.pk).name == 'Renombrada'

    def test_it_returns_self(self, rule):
        assert rule.write(name='Otra vez') is rule

    def test_a_critical_field_refreshes_cron_and_registry(self, rule, monkeypatch):
        llamadas = []
        monkeypatch.setattr(BaseAutomation, '_update_cron',
                            lambda self: llamadas.append('cron'))
        monkeypatch.setattr(BaseAutomation, '_update_registry',
                            lambda self: llamadas.append('registry'))
        rule.write(active=False)
        assert llamadas == ['cron', 'registry']

    def test_a_range_field_refreshes_only_the_cron(self, rule, monkeypatch):
        """La asimetría que ``save()`` no puede ver: sólo el cron."""
        llamadas = []
        monkeypatch.setattr(BaseAutomation, '_update_cron',
                            lambda self: llamadas.append('cron'))
        monkeypatch.setattr(BaseAutomation, '_update_registry',
                            lambda self: llamadas.append('registry'))
        rule.write(trg_date_range=3)
        assert llamadas == ['cron']

    def test_an_indifferent_field_refreshes_neither(self, rule, monkeypatch):
        llamadas = []
        monkeypatch.setattr(BaseAutomation, '_update_cron',
                            lambda self: llamadas.append('cron'))
        monkeypatch.setattr(BaseAutomation, '_update_registry',
                            lambda self: llamadas.append('registry'))
        rule.write(name='Indiferente')
        assert llamadas == []


class TestUnlink:
    """≙ ``unlink`` (``:513-521``) — el nombre de la fuente sobre ``delete``."""

    def test_it_removes_the_row(self, rule):
        pk = rule.pk
        rule.unlink()
        assert not BaseAutomation.objects.filter(pk=pk).exists()

    def test_it_refreshes_cron_and_registry(self, rule, monkeypatch):
        llamadas = []
        monkeypatch.setattr(BaseAutomation, '_update_cron',
                            lambda self: llamadas.append('cron'))
        monkeypatch.setattr(BaseAutomation, '_update_registry',
                            lambda self: llamadas.append('registry'))
        rule.unlink()
        assert llamadas == ['cron', 'registry']


class TestUsageSelectionAdd:
    """≙ ``usage = fields.Selection(selection_add=[('base_automation', …)])``."""

    def test_the_value_is_in_the_vocabulary(self):
        valores = [v for v, __ in
                   IrActionsServer._meta.get_field('usage').choices]
        assert USAGE_BASE_AUTOMATION in valores

    def test_the_previous_vocabulary_survives(self):
        """``selection_add`` AMPLÍA: no sustituye lo que ``base`` declaró."""
        valores = [v for v, __ in
                   IrActionsServer._meta.get_field('usage').choices]
        assert 'ir_actions_server' in valores

    def test_the_ondelete_policy_travels_with_the_value(self):
        politica = getattr(IrActionsServer._meta.get_field('usage'),
                           'ondelete', None)
        assert politica is not None
        assert politica[USAGE_BASE_AUTOMATION] == 'cascade'


class TestWarningDepends:
    """≙ ``_warning_depends`` (``:20-25``) — ACUMULA sobre la base."""

    def test_the_two_names_of_the_addon_are_there(self):
        depende = IrActionsServer._warning_depends()
        assert 'model_id' in depende
        assert 'base_automation_id' in depende

    def test_the_names_of_base_survive(self):
        """ACUMULA: lo que ``base`` declaraba sigue en la lista."""
        assert len(IrActionsServer._warning_depends()) > 2


class TestGetWarningMessages:
    """≙ ``_get_warning_messages`` (``:27-39``) — el aviso de modelo dispar."""

    def test_a_mismatched_model_warns(self, rule, partner_model):
        otro = IrModel.objects.filter(model='base.ResUsers').first() or \
            IrModel.objects.create(model='base.ResUsers', name='Usuario')
        action = IrActionsServer.objects.create(
            name='Acción dispar', state='object_create',
            model_name=otro.model)
        BaseAutomationAction.objects.create(action=action, automation=rule)
        avisos = action._get_warning_messages()
        assert any('Acción dispar' in aviso for aviso in avisos)

    def test_a_matching_model_does_not_warn(self, rule, partner_model):
        action = IrActionsServer.objects.create(
            name='Acción alineada', state='object_create',
            model_name=partner_model.model)
        BaseAutomationAction.objects.create(action=action, automation=rule)
        assert not any('Acción alineada' in aviso
                       for aviso in action._get_warning_messages())

    def test_an_action_without_a_rule_does_not_warn(self, partner_model):
        action = IrActionsServer.objects.create(
            name='Suelta', state='object_create', model_name='base.ResUsers')
        assert not any('Suelta' in aviso
                       for aviso in action._get_warning_messages())


class TestGetChildrenDomain:
    """≙ ``_get_children_domain`` (``:41-45``) — una hija no es de una regla."""

    def test_it_adds_the_condition_over_the_link(self):
        assert 'base_automation_link' in repr(
            IrActionsServer._get_children_domain())

    def test_the_conditions_of_base_survive(self):
        """``super() & …``: lo que la base acotaba sigue acotando."""
        dominio = repr(IrActionsServer._get_children_domain())
        assert 'parent_id' in dominio


class TestComputeAvailableModelIds:
    """≙ ``_compute_available_model_ids`` (``:47-53``) — límite estricto."""

    def test_without_the_automation_usage_the_base_universe_survives(self):
        action = IrActionsServer.objects.create(
            name='Normal', state='object_create', usage='ir_actions_server')
        assert len(action._compute_available_model_ids()) > 1

    def test_with_the_automation_usage_it_narrows_to_the_rule_model(
            self, rule, partner_model):
        action = IrActionsServer.objects.create(
            name='De regla', state='object_create',
            usage=USAGE_BASE_AUTOMATION)
        BaseAutomationAction.objects.create(action=action, automation=rule)
        assert action._compute_available_model_ids() == [partner_model.pk]

    def test_with_the_usage_and_no_rule_it_narrows_to_nothing(self):
        """La asimetría de la fuente: si el modelo no estaba, queda vacío."""
        action = IrActionsServer.objects.create(
            name='Sin regla', state='object_create',
            usage=USAGE_BASE_AUTOMATION)
        assert action._compute_available_model_ids() == []


class TestGetEvalContext:
    """≙ ``_get_eval_context`` (``:55-62``) — ``json`` sólo en modo código."""

    def test_code_state_publishes_json(self):
        action = IrActionsServer.objects.create(
            name='Código', state='code', code='x = 1')
        assert 'json' in action._get_eval_context()

    def test_another_state_does_not_publish_json(self):
        action = IrActionsServer.objects.create(
            name='No código', state='object_create')
        assert 'json' not in action._get_eval_context()

    def test_the_context_of_base_survives(self):
        """``super()`` primero: lo que la base ponía sigue puesto."""
        action = IrActionsServer.objects.create(
            name='Código dos', state='code', code='x = 1')
        contexto = action._get_eval_context()
        assert len(contexto) > 1


class TestAutomationOfHelper:
    """El ayudante que sustituye a ``action.base_automation_id``."""

    def test_it_finds_the_linked_rule(self, rule):
        action = IrActionsServer.objects.create(
            name='Ligada', state='object_create')
        BaseAutomationAction.objects.create(action=action, automation=rule)
        assert _automation_of(action) == rule

    def test_without_a_link_it_is_none(self):
        action = IrActionsServer.objects.create(
            name='Sin ligar', state='object_create')
        assert _automation_of(action) is None
