"""Los cómputos, restricciones y onchanges de ``crm.lead`` sobre recordsets.

La fuente itera ``for lead in self`` en cada uno
(``odoo19c: addons/crm/models/crm_lead.py``), y el ORM los invoca con el
recordset entero (``_compute_field_value`` y ``_validate_fields``). Escritos
para un solo registro, cualquier alta o ``write`` de dos iniciativas moría
con ``Expected singleton``. Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
crm-lead-recordset-computes.md``.

*Métrica:* altas y escrituras de dos iniciativas, y el valor calculado de
cada una.
*Ciega a:* la lógica de cada cómputo sobre un registro, que no cambia.
"""
import pytest

from addons.crm.models import CrmLead
from exceptions import ValidationError
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


def _two(**vals):
    with sudo():
        return env()['crm.lead'].create(
            [{'name': 'CMR Uno', **vals}, {'name': 'CMR Dos', **vals}])


def test_two_leads_are_created_at_once():
    leads = _two(email_from='uno@cmr.mx', expected_revenue=7)
    with sudo():
        assert len(leads) == 2
        assert leads.mapped('expected_revenue') == [7, 7]


@pytest.mark.parametrize('vals', [
    {'name': 'CMR Otra'},
    {'email_from': 'otra@cmr.mx'},
    {'phone': '+52 55 1234 5678'},
    {'expected_revenue': 10},
    {'probability': 50},
    {'recurring_revenue': 5},
])
def test_two_leads_are_written_at_once(vals):
    leads = _two()
    with sudo():
        leads.write(vals)
        leads.flush_recordset()
        field, value = next(iter(vals.items()))
        assert leads.mapped(field) == [value] * 2


def test_the_won_constraint_checks_each_lead():
    """``write`` fija la probabilidad en 100 al pasar a una etapa ganada,
    como la fuente; la restricción se ejercita directamente sobre las dos
    iniciativas con la etapa puesta por SQL."""
    leads = _two(probability=10)
    with sudo():
        won = env()['crm.stage'].create(
            [{'name': 'CMR Ganada', 'is_won': True, 'sequence': 999}])
        CrmLead.objects.filter(pk__in=leads.ids).update(stage_id=won.id)
        # El recálculo que dispara la invalidación ya valida las dos.
        with pytest.raises(ValidationError):
            leads.invalidate_recordset()
            leads._check_won_validity()
