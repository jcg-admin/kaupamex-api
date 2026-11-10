"""Métodos base de ``BaseModel`` con recordset, contra ``odoo19c``.

La rejilla (``tests/fixtures/model_record_grid.py``) recibe
``env['ir.attachment']`` en los dos lados, sobre una base con ``base``;
toma el método de ``BaseModel``, no del modelo, porque
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

from orm.environments import env as current_env
from orm.environments import sudo

from tests.fixtures import model_record_grid, reference_process

pytestmark = [pytest.mark.reference, pytest.mark.django_db]

GRID = pathlib.Path(model_record_grid.__file__)
MODEL = 'ir.attachment'


@pytest.fixture(scope='module')
def reference_trace():
    reference_process.require()
    return reference_process.trace(GRID, MODEL, 'user')


def _ours():
    """La referencia corre como ``admin`` (modo ``'user'``), que tiene la
    ACL de ``ir.attachment``. Este árbol no siembra usuarios, y sin actor la
    lectura de la base comprueba la ACL como ``fetch`` (TASK-API-0182) y
    deniega: el paso del id inexistente lo medía. El equivalente del actor
    con acceso es el bloque elevado."""
    with sudo():
        return model_record_grid.trace(None, current_env()[MODEL], MODEL)


def test_the_trace_matches_the_reference(reference_trace):
    ours = _ours()
    assert len(ours) == len(reference_trace)
    differences = [(theirs, mine) for theirs, mine
                   in zip(reference_trace, ours) if theirs != mine]
    assert differences == []


def test_only_the_non_singletons_raise(reference_trace):
    """Cero o dos registros rehúsan por ``ensure_one``; uno responde, y
    ningún paso de los alias rehúsa."""
    raising = [line for line in reference_trace if ' raises ' in line
               and line.startswith('can_return')]
    assert len(raising) == 6
    assert all(line.endswith('raises ValueError') for line in raising)
    others = [line for line in reference_trace if ' raises ' in line
              and not line.startswith('can_return')]
    assert others == ['convert_to_record unknown field raises KeyError',
                      'read_format unknown field raises KeyError']
    assert all(' 1 ' in line for line in reference_trace
               if line not in raising and line.startswith('can_return'))
