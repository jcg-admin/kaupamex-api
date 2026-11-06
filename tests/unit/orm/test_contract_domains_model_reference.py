"""``Domain.optimize`` con modelo, contra el ORM real de ``odoo19c``.

Los diferenciales de ``test_contract_domains_reference.py`` cubren lo que no
necesita modelo. Esta prueba cubre lo que sí: el despacho de los
optimizadores por tipo de campo (booleano, texto, relacional, entero), la
normalización de valores contra el campo y la conversión ``any`` → ``any!``
que decide si la subconsulta del comodelo aplica permisos.

La rejilla (``tests/fixtures/model_domain_grid.py``) se ejecuta tal cual en
los dos lados: en la referencia, en un subproceso con su propio intérprete y
un ``Registry`` sobre una base con ``base`` (``reference_process``); aquí,
con ``orm.domains.Domain`` sobre ``IrRule``. Se comparan las trazas cadena a
cadena, en dos modos: sin elevación y con ella, porque
``_optimize_any_with_rights`` lee ``env.su`` en la referencia e ``is_su()``
aquí.

*Métrica:* ``repr`` del resultado de ``optimize`` y ``optimize_full``, o la
clase de la excepción, para 286 condiciones sobre seis campos de
``ir.rule``, solas y negadas, en los dos modos.
*Ciega a:* los campos de ``ir.rule`` que no comparten tipo en los dos árboles
(``model_id`` many2one contra ``model_name`` char); los optimizadores de
fecha, binario y propiedades, que ``ir.rule`` no ejercita; el texto de los
mensajes de error, del que sólo se compara la clase.
"""
import pathlib

import pytest

from addons.base.models.ir_rule import IrRule
from orm.domains import Domain
from orm.environments import sudo
from tests.fixtures import model_domain_grid, reference_process

pytestmark = pytest.mark.reference

GRID = pathlib.Path(model_domain_grid.__file__)
MODEL = 'ir.rule'
#: Pasos en que la referencia levanta, por modo: la comparación de clases de
#: excepción sólo cuenta si las dos trazas producen además valores.
STEPS_THAT_RAISE = 72


def _ours(mode):
    if mode == 'su':
        with sudo():
            return model_domain_grid.trace(Domain, IrRule)
    return model_domain_grid.trace(Domain, IrRule)


@pytest.fixture(scope='module')
def reference_traces():
    reference_process.require()
    return {mode: reference_process.trace(GRID, MODEL, mode)
            for mode in ('user', 'su')}


@pytest.mark.parametrize('mode', ['user', 'su'])
def test_the_trace_matches_the_reference(reference_traces, mode):
    reference = reference_traces[mode]
    ours = _ours(mode)
    assert len(ours) == len(reference)
    differences = [(theirs, mine) for theirs, mine in zip(reference, ours)
                   if theirs != mine]
    assert differences == []


@pytest.mark.parametrize('mode', ['user', 'su'])
def test_the_comparison_is_not_made_of_errors(reference_traces, mode):
    raising = [line for line in reference_traces[mode] if ' raises ' in line]
    assert len(raising) == STEPS_THAT_RAISE
    assert len(reference_traces[mode]) - len(raising) > 0


def test_the_elevation_mode_changes_the_reference(reference_traces):
    """Control: los dos modos difieren en la referencia, o el modo no mide."""
    changed = [line for line, other in zip(reference_traces['user'],
                                           reference_traces['su'])
               if line != other]
    assert changed
    assert all("'any'" in line or "'not any'" in line for line in changed)
