"""Campos relacionales de ``BaseModel``, contra ``odoo19c``.

La rejilla (``tests/fixtures/model_relational_grid.py``) recibe
``env['test_orm.category']`` en los dos lados.
La base de referencia tiene que traer ``test_orm`` instalado
(``orm_refproc_test_orm``, que inicializa
``scripts/workbench/reference-environment-isolated-20261106T071536/``); con
la base que sólo trae ``base`` la referencia no conoce el modelo y la prueba
falla, no se omite.

*Métrica:* el ``repr`` de cada paso, con los ids nuevos reducidos a su clase.
*Ciega a:* los ``Many2one`` con valor persistido, cuyo ``display_name`` lee la
base, y a ``Many2many``/``One2many``, que esta rejilla no pregunta.
"""
import pathlib

import pytest

from orm.environments import env as current_env
from tests.fixtures import model_relational_grid, reference_process

pytestmark = [pytest.mark.reference, pytest.mark.django_db]

GRID = pathlib.Path(model_relational_grid.__file__)
MODEL = 'test_orm.category'


@pytest.fixture(scope='module')
def reference_trace():
    reference_process.require()
    return reference_process.trace(GRID, MODEL, 'user')


def _ours():
    return model_relational_grid.trace(None, current_env()[MODEL], MODEL)


def test_the_trace_matches_the_reference(reference_trace):
    ours = _ours()
    assert len(ours) == len(reference_trace)
    differences = [(theirs, mine) for theirs, mine
                   in zip(reference_trace, ours) if theirs != mine]
    assert differences == []


def test_the_display_mode_changes_the_answer(reference_trace):
    """Con valor, ``display=True`` da el par y ``False`` sólo el id: es lo
    que hace que la rejilla discrimine ``use_display_name``."""
    by_name = dict(line.split(' ', 3)[2:] for line in reference_trace
                   if line.startswith('convert_to_read value'))
    assert by_name == {'display=True': "('NewId', 'P')",
                       'display=False': "'NewId'"}
