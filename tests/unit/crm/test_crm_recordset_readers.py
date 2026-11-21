"""Los lectores de ``tag_ids`` y ``team_ids`` de ``crm`` como recordsets.

``crm.lead``, ``crm.stage``, ``crm.team`` y ``crm.tag`` son ``BaseModel``,
así que sus Many2many son recordsets, como en la fuente; estos sitios los
leían con el gestor de Django (``all``, ``filter``, ``first``). Diseño:
``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
basemodel-reverse-queryset.md``.

≙ ``_compute_stage_id`` (``odoo19c: addons/crm/models/crm_lead.py:353-357``),
``_merge_get_fields_specific`` (``:1609-1618``),
``_pls_get_lead_pls_values`` (``:2729-2811``) y
``prepare_pls_tooltip_data`` (``:2813-2890``).

*Métrica:* cada lector sobre registros creados por el ORM.
*Ciega a:* la calibración de las frecuencias del scoring, que no se ejercita.
"""
import pytest

from addons.base.models.ir_config_parameter import SystemParameter
from addons.crm.models import CrmLead
from orm.environments import env, sudo

pytestmark = pytest.mark.django_db


@pytest.fixture
def lead_with_tags():
    with sudo():
        tags = env()['crm.tag'].create([{'name': 'CRR Uno'},
                                        {'name': 'CRR Dos'}])
        [lead] = env()['crm.lead'].create(
            [{'name': 'CRR Lead', 'tag_ids': [(6, 0, tags.ids)]}])
    return lead, tags


def test_a_stage_of_another_team_is_replaced(lead_with_tags):
    with sudo():
        team_a, team_b = env()['crm.team'].create(
            [{'name': 'CRR A'}, {'name': 'CRR B'}])
        general, only_b = env()['crm.stage'].create([
            {'name': 'CRR General', 'sequence': 1},
            {'name': 'CRR Sólo B', 'sequence': 0,
             'team_ids': [(6, 0, [team_b.id])]},
        ])
        # De una en una: el bloque de cómputos y restricciones de
        # ``crm.lead`` supone un solo registro (sucesor
        # ``crm-lead-recordset-computes-0397``).
        [lead_a] = env()['crm.lead'].create(
            [{'name': 'CRR en A', 'team_id': team_a.id,
              'stage_id': only_b.id}])
        [lead_b] = env()['crm.lead'].create(
            [{'name': 'CRR en B', 'team_id': team_b.id,
              'stage_id': only_b.id}])
        lead_a._compute_stage_id()
        lead_b._compute_stage_id()
        assert lead_a.stage_id != only_b
        assert lead_b.stage_id == only_b


def test_merge_collects_the_tags_of_the_leads(lead_with_tags):
    lead, tags = lead_with_tags
    with sudo():
        merge = CrmLead._merge_get_fields_specific()['tag_ids']
        assert {t.id for t in merge('tag_ids', lead)} == set(tags.ids)


def test_pls_values_carry_each_tag(lead_with_tags):
    lead, tags = lead_with_tags
    SystemParameter.set_param('crm.pls_fields', 'tag_ids')
    with sudo():
        values = CrmLead._pls_get_lead_pls_values(lead)[lead.id]['values']
    assert sorted(v for f, v in values if f == 'tag_id') == sorted(tags.ids)


def test_the_tooltip_names_the_tag(lead_with_tags, monkeypatch):
    lead, tags = lead_with_tags
    tag = tags[0]

    def scores(cls, leads, is_tooltip=False):
        return None, {'scores': [(0.9, 'tag_id', tag.id)],
                      'probability': 75.0}

    monkeypatch.setattr(CrmLead, '_pls_get_naive_bayes_probabilities',
                        classmethod(scores))
    with sudo():
        data = lead.prepare_pls_tooltip_data()
    assert data['top_3_data'][0]['value'] == tag.name
