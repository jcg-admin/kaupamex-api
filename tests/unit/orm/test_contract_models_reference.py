"""Piezas de ``models.py`` sin modelo ni base, contra ``odoo19c``.

La rejilla (``tests/fixtures/models_grid.py``) recibe el módulo de modelos:
``odoo.orm.models`` en el proceso de referencia (sin base ni cursor) y
``orm.models`` aquí. Cubre ``fix_import_export_id_paths`` sobre diez rutas,
``itemgetter_tuple`` con cero, uno y dos elementos, ``ReversibleComparator``
(orden con ``None`` y con inversión en sus cuatro combinaciones, igualdad,
``hash``, ``repr``, ``__slots__`` y la comparación entre tipos que no se
ordenan) y los valores por defecto de 22 atributos de clase de
``BaseModel``.

*Métrica:* el ``repr`` de cada paso, o la clase de su excepción.
*Ciega a:* ``check_company_domain_parent_of`` y
``check_companies_domain_parent_of``, cuya rama principal lee
``parent_path`` de la base; y los atributos de clase que cada modelo
concreto sobreescribe, que dependen del addon.
"""
import pathlib

import pytest

import orm.models as models_module
from tests.fixtures import models_grid, reference_process

pytestmark = pytest.mark.reference

GRID = pathlib.Path(models_grid.__file__)


@pytest.fixture(scope='module')
def reference_trace():
    reference_process.require()
    return reference_process.trace(GRID, 'models', 'user')


def test_the_trace_matches_the_reference(reference_trace):
    ours = models_grid.trace(models_module)
    assert len(ours) == len(reference_trace)
    differences = [(theirs, mine) for theirs, mine
                   in zip(reference_trace, ours) if theirs != mine]
    assert differences == []


def test_the_comparison_is_not_made_of_errors(reference_trace):
    raising = [line for line in reference_trace if ' raises ' in line]
    assert len(raising) == 3
    assert len(reference_trace) > len(raising)
