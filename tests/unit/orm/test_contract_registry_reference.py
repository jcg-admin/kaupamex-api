"""``TriggerTree``, ``DummyRLock`` y ``_unaccent`` contra ``odoo19c``.

La rejilla (``tests/fixtures/registry_grid.py``) recibe el módulo del
registro: ``odoo.orm.registry`` en el proceso de referencia (sin base ni
cursor) y ``orm.registry`` aquí. Cubre el árbol de disparadores del docstring
de la fuente (G, ``X.F``, ``W.X.F``, ``Y.F``), su ``__bool__``, ``increase``,
``depth_first``, ``merge`` con y sin ``select``, ``__slots__``, el cerrojo
nulo y ``_unaccent`` en sus tres ramas: texto, ``SQL`` (código y parámetros,
anidado y compuesto dos veces) y ``Composable`` (``Identifier``,
``Composed``, ``Literal``), más dos entradas de otro tipo.

*Métrica:* el ``repr`` de cada paso, o la clase de su excepción.
*Ciega a:* la cadena SQL que un ``Composed`` produce al renderizarse, que
exige una conexión (aquí se compara su ``repr``, que nombra cada pieza); y los
``TriggerTree`` con campos reales, que el registro construye a partir de los
modelos.
"""
import pathlib

import pytest
from psycopg import sql as composable

import orm.registry as registry_module
from tests.fixtures import reference_process, registry_grid

pytestmark = pytest.mark.reference

GRID = pathlib.Path(registry_grid.__file__)


@pytest.fixture(scope='module')
def reference_trace():
    reference_process.require()
    return reference_process.trace(GRID, 'registry', 'user')


def test_the_trace_matches_the_reference(reference_trace):
    ours = registry_grid.trace(registry_module, composable)
    assert len(ours) == len(reference_trace)
    differences = [(theirs, mine) for theirs, mine
                   in zip(reference_trace, ours) if theirs != mine]
    assert differences == []


def test_the_comparison_is_not_made_of_errors(reference_trace):
    raising = [line for line in reference_trace if ' raises ' in line]
    assert len(raising) == 1
    assert len(reference_trace) > len(raising)
