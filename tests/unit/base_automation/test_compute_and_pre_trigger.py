"""La precondición se evalúa antes de escribir, y un recálculo almacenado
dispara las reglas de escritura.

≙ ``odoo19c: addons/base_automation/models/base_automation.py``:
``make_write`` (``:880-907``) lee ``_filter_pre`` y los valores viejos
ANTES de ``write.origin``; ``make_compute_field_value`` (``:909-946``) hace
lo mismo alrededor del recálculo. Aquí el recálculo llega por
``save(update_fields)`` desde ``_write_multi``. Diseño en
``designs/base-automation-compute-trigger.md``.

*Métrica:* llamadas a ``IrActionsServer.run`` de la acción de la regla, que
``_process`` invoca una vez por registro que pasa los filtros.
*Ciega a:* lo que la acción hace: este árbol no ejecuta su cuerpo.
"""
import pytest

from addons.base.models import IrActionsServer, IrModel, ResCompany, ResPartner
from addons.base_automation.models.base_automation import (
    BaseAutomation,
    BaseAutomationAction,
)
from addons.resource.models import ResourceCalendar
from orm.environments import sudo

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _as_superuser():
    with sudo():
        yield


@pytest.fixture
def runs(monkeypatch):
    """Cada ejecución de una acción de servidor, en orden."""
    calls = []
    monkeypatch.setattr(IrActionsServer, 'run',
                        lambda self, *a, **k: calls.append(self.pk))
    return calls


def _rule(model_label, **values):
    ir_model = IrModel.objects.filter(model=model_label).first() or (
        IrModel.objects.create(model=model_label, name=model_label))
    rule = BaseAutomation.objects.create(
        name='Regla', model_id=ir_model, trigger='on_write', **values)
    action = IrActionsServer.objects.create(
        name='Espía', state='object_create', model_name=model_label)
    BaseAutomationAction.objects.create(action=action, automation=rule)
    return action


def test_the_precondition_sees_the_value_before_the_write(runs):
    partner = ResPartner.objects.create(name='Antes')
    action = _rule('res.partner',
                   filter_pre_domain="[('name', '=', 'Antes')]")
    partner.name = 'Después'
    partner.save()
    assert runs == [action.pk]


def test_a_record_that_only_matches_after_the_write_does_not_fire(runs):
    partner = ResPartner.objects.create(name='Otro')
    _rule('res.partner', filter_pre_domain="[('name', '=', 'Antes')]")
    partner.name = 'Antes'
    partner.save()
    assert runs == []


@pytest.fixture
def calendar():
    company = ResCompany.objects.create(code='acme-auto', name='ACME')
    record = ResourceCalendar.objects.create(name='Est', company=company)
    record.create_default_attendances()
    record.flush_model()
    return record


def _lengthen_one_attendance(calendar):
    attendance = calendar.attendances.filtered(
        lambda a: a.day_period == 'afternoon')[:1]
    attendance.write({'hour_to': attendance.hour_to + 1})
    calendar.flush_model()


def test_each_stored_recompute_method_fires_the_write_rule(runs, calendar):
    """``hours_per_day`` y ``hours_per_week`` tienen un método cada uno:
    son dos llamadas a ``_compute_field_value``, y la marca
    ``__action_done`` de la fuente vive en el contexto de cada llamada
    (``base_automation.py:781-797``), así que allí la regla también corre
    una vez por método."""
    action = _rule('resource.calendar')
    _lengthen_one_attendance(calendar)
    assert runs == [action.pk, action.pk]


def test_the_postcondition_filters_the_recomputed_value(runs, calendar):
    _rule('resource.calendar',
          filter_domain="[('hours_per_day', '>', 9)]")
    _lengthen_one_attendance(calendar)
    assert runs == []


def test_the_postcondition_sees_the_recomputed_value(runs, calendar):
    """Sólo el valor nuevo (41 h) cumple el filtro; la base tenía 40. Sin
    volcar antes de la postcondición, la consulta leería 40 y no correría."""
    action = _rule('resource.calendar',
                   filter_domain="[('hours_per_week', '>', 40.5)]")
    _lengthen_one_attendance(calendar)
    assert action.pk in runs
