"""Métodos base de ``BaseModel`` con recordset, contra ``odoo19c``.

La rejilla (``tests/fixtures/model_record_grid.py``) recibe en la referencia
``env['ir.attachment']`` sobre una base con ``base`` y aquí la clase del
mismo ``_name``; toma el método de ``BaseModel``, no del modelo, porque
``ir.attachment`` redefine ``_can_return_content`` en la fuente y el
contrato que se mide es el de la base.

*Métrica:* el ``repr`` de cada paso, o la clase de su excepción.
*Ciega a:* los overrides de addons (``ir.attachment``, ``website``,
``point_of_sale``…), que conceden acceso, y a su consumidor
``ir.binary._find_record``, cuyo bypass por token es divergencia declarada
por DEC-11 en ``src/addons/base/models/ir_binary.py``.
"""
import pathlib

import pytest
from django.apps import apps

from tests.fixtures import model_record_grid, reference_process

pytestmark = [pytest.mark.reference, pytest.mark.django_db]

GRID = pathlib.Path(model_record_grid.__file__)
MODEL = 'ir.attachment'


@pytest.fixture(scope='module')
def reference_trace():
    reference_process.require()
    return reference_process.trace(GRID, MODEL, 'user')


def _ours():
    model = next(model for model in apps.get_models()
                 if getattr(model, '_name', None) == MODEL)
    return model_record_grid.trace(None, model, MODEL)


def test_the_trace_matches_the_reference(reference_trace):
    ours = _ours()
    assert len(ours) == len(reference_trace)
    differences = [(theirs, mine) for theirs, mine
                   in zip(reference_trace, ours) if theirs != mine]
    assert differences == []


def test_only_the_non_singletons_raise(reference_trace):
    """Cero o dos registros rehúsan por ``ensure_one``; uno responde."""
    raising = [line for line in reference_trace if ' raises ' in line]
    assert len(raising) == 6
    assert all(line.endswith('raises ValueError') for line in raising)
    assert all(' 1 ' in line for line in reference_trace
               if line not in raising)
