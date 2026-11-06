"""Piezas de ``environments.py`` sin cursor, contra ``odoo19c``.

La rejilla (``tests/fixtures/environments_module_grid.py``) recibe el módulo
de entornos: ``odoo.orm.environments`` en el proceso de referencia, sin base
ni cursor, y ``orm.environments`` aquí. Cubre ``Starred``
(``odoo19c: odoo/orm/environments.py:956-964``).

*Métrica:* el ``repr`` de cada paso, o la clase de su excepción.
*Ciega a:* todo lo que necesita un ``Environment`` o una transacción, que
mide ``test_contract_environments_reference.py``.
"""
import pathlib

import pytest

import orm.environments as environments_module
from tests.fixtures import environments_module_grid, reference_process

pytestmark = pytest.mark.reference

GRID = pathlib.Path(environments_module_grid.__file__)


@pytest.fixture(scope='module')
def reference_trace():
    reference_process.require()
    return reference_process.trace(GRID, 'environments', 'user')


def test_the_trace_matches_the_reference(reference_trace):
    ours = environments_module_grid.trace(environments_module)
    assert len(ours) == len(reference_trace)
    differences = [(theirs, mine) for theirs, mine
                   in zip(reference_trace, ours) if theirs != mine]
    assert differences == []


def test_the_comparison_is_not_made_of_errors(reference_trace):
    """Sólo el atributo que las ranuras no declaran rehúsa."""
    raising = [line for line in reference_trace if ' raises ' in line]
    assert raising == ['setattr other raises AttributeError']
    assert len(reference_trace) > len(raising)
