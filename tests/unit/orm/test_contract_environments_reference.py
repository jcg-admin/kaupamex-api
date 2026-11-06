"""``Environment`` contra el ORM real de ``odoo19c``.

La rejilla (``tests/fixtures/environment_grid.py``) se ejecuta en los dos
lados con una fábrica de entornos: en la referencia, sobre un cursor de la
base desechable con ``base`` (``reference_process``); aquí, con
``orm.environments.Environment``. Cubre la agrupación por ejes de ``__new__``,
la elevación implícita del uid 1, la identidad, la guarda de ``__setattr__``,
la pertenencia de un modelo, ``__call__`` (contexto, elevación y limpieza del
contexto al elevar), ``lang`` y ``tz`` leídos del contexto del entorno, e
``is_superuser``.

*Métrica:* el ``repr`` de cada paso, o la clase de su excepción; el contexto
como pares ordenados y la zona como ``str``.
*Ciega a:* lo que depende de los datos de cada base (``env.user``,
``company``, ``ref``), el contenido del registro (``__iter__``/``__len__``,
que cuentan modelos distintos en cada árbol) y el texto de los mensajes.
"""
import pathlib

import pytest

from orm.environments import Environment
from tests.fixtures import environment_grid, reference_process

pytestmark = [pytest.mark.reference, pytest.mark.django_db]

GRID = pathlib.Path(environment_grid.__file__)


@pytest.fixture(scope='module')
def reference_trace():
    reference_process.require()
    return reference_process.trace(GRID, 'environment', 'user')


def _ours():
    return environment_grid.trace(
        lambda uid, context, su: Environment(None, uid, context, su))


def test_the_trace_matches_the_reference(reference_trace):
    ours = _ours()
    assert len(ours) == len(reference_trace)
    differences = [(theirs, mine) for theirs, mine
                   in zip(reference_trace, ours) if theirs != mine]
    assert differences == []


def test_the_comparison_is_not_made_of_errors(reference_trace):
    raising = [line for line in reference_trace if ' raises ' in line]
    assert len(raising) == 4
    assert len(reference_trace) > len(raising)
