"""Sonda: lo que ``crm.lead`` HACE ante tres contratos de ``BaseModel``.

No afirma nada: registra el resultado observado junto al esperado por la
referencia (``odoo19c: odoo/orm/models.py``) y lo escribe en
``outputs/crm_lead_behaviour.json``. Las pruebas que sí afirman viven en
``tests/integration/crm/test_basemodel_contract_reach.py``; aquí van los
contratos cuya divergencia se mide antes de decidir quién la cierra.

Uso, desde la raíz del repo::

    .venv/bin/python -m pytest -q --reuse-db -p no:cacheprovider \\
        "$BENCH/probes/test_probe_crm_lead_behaviour.py"
"""
import json
import pathlib

import pytest

from addons.crm.models import CrmLead

OUTPUT = pathlib.Path(__file__).resolve().parent.parent / 'outputs'


def _outcome(call):
    try:
        return {'returned': repr(call())}
    except Exception as error:
        return {'raised': f'{type(error).__name__}: {error}'}


@pytest.mark.django_db
def test_record_crm_lead_behaviour():
    lead = CrmLead.objects.create(name='Sonda de alcance')
    rows = {
        'action_archive': {
            'expected': 'active pasa a False (models.py:5797-5806)',
            **_outcome(lambda: lead.action_archive()),
        },
        'write_unknown_field': {
            'expected': "ValueError('Invalid field ...') (models.py write)",
            **_outcome(lambda: lead.write({'no_such_field': 1})),
        },
        'write_return_value': {
            'expected': 'True (models.py write)',
            **_outcome(lambda: lead.write({'name': 'Sonda renombrada'})),
        },
    }
    lead.refresh_from_db()
    rows['action_archive']['active_after'] = lead.active
    (OUTPUT / 'crm_lead_behaviour.json').write_text(
        json.dumps(rows, indent=2, ensure_ascii=False) + '\n')
