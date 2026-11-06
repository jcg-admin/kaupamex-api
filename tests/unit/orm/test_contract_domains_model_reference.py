"""``Domain.optimize`` con modelo, contra el ORM real de ``odoo19c``.

Los diferenciales de ``test_contract_domains_reference.py`` cubren lo que no
necesita modelo. Esta prueba cubre lo que sí: el despacho de los
optimizadores por tipo de campo (booleano, texto, relacional, entero), la
normalización de valores contra el campo y la conversión ``any`` → ``any!``
que decide si la subconsulta del comodelo aplica permisos.

La rejilla (``tests/fixtures/model_domain_grid.py``) se ejecuta tal cual en
los dos lados: en la referencia, en un subproceso con su propio intérprete y
un ``Registry`` sobre una base con ``base`` (``reference_process``); aquí,
con ``orm.domains.Domain`` sobre el modelo del mismo ``_name``. Se comparan
las trazas cadena a cadena. ``ir.rule`` va en dos modos —sin elevación y con
ella— porque ``_optimize_any_with_rights`` lee ``env.su`` en la referencia e
``is_su()`` aquí; los modelos con fechas van en dos husos, porque la
conversión de una fecha a fecha-hora lee ``env.tz``.

*Métrica:* ``repr`` del resultado de ``optimize``, ``optimize_full`` y
``validate``, o la clase de la excepción, más ``iter``, ``==`` y
``map_conditions`` de cada par sin optimizar. En ``ir.rule``: 286 condiciones
(solas y negadas) y 1 172 pares unidos con ``&`` y ``|`` (solos y negados),
17 838 pasos por modo de elevación. En ``ir.cron`` (fecha-hora) y
``res.currency.rate`` (fecha): 800 y 210 pasos por huso, UTC y
``America/Mexico_City``. En ``res.partner`` (``image_1920``, many2one con
fusión de ``any`` bajo ``&``, texto): 13 200 pasos.
*Ciega a:* los campos que no comparten nombre y tipo en los dos árboles; los
valores relativos al instante (``now``), que difieren entre dos procesos —
``'today'`` sí entra, y una ejecución que cruce la medianoche del huso
entre los dos procesos daría una diferencia que no es del puerto—; el
operador ``child_of``, cuyo resultado depende de los datos de cada base; el
texto de los mensajes de error, del que sólo se compara la clase.
"""
import pathlib

import pytest
from django.apps import apps

from orm.domains import Domain
from orm.environments import context_scope, sudo
from tests.fixtures import model_domain_grid, reference_process

pytestmark = pytest.mark.reference

GRID = pathlib.Path(model_domain_grid.__file__)
MEXICO = 'America/Mexico_City'
UTC = 'UTC'
#: (modelo, modo, huso) y los pasos que levantan en la referencia: la
#: comparación de clases de excepción sólo cuenta si además hay valores.
CASES = {
    ('ir.rule', 'user', None): 3290,
    ('ir.rule', 'su', None): 3290,
    ('ir.cron', 'user', UTC): 120,
    ('ir.cron', 'user', MEXICO): 120,
    ('res.currency.rate', 'user', UTC): 60,
    ('res.currency.rate', 'user', MEXICO): 60,
    ('res.partner', 'user', UTC): 3900,
}
IDS = [f'{model}-{mode}-{tz or "-"}' for model, mode, tz in CASES]


def _model(name):
    return next(model for model in apps.get_models()
                if getattr(model, '_name', None) == name)


def _context(tz):
    return {'tz': tz} if tz else {}


def _ours(model_name, mode, tz):
    model = _model(model_name)
    with context_scope(**_context(tz)):
        if mode == 'su':
            with sudo():
                return model_domain_grid.trace(Domain, model, model_name)
        return model_domain_grid.trace(Domain, model, model_name)


@pytest.fixture(scope='module')
def reference_traces():
    reference_process.require()
    return {case: reference_process.trace(GRID, case[0], case[1],
                                          _context(case[2]))
            for case in CASES}


@pytest.mark.parametrize('case', CASES, ids=IDS)
def test_the_trace_matches_the_reference(reference_traces, case):
    reference = reference_traces[case]
    ours = _ours(*case)
    assert len(ours) == len(reference)
    differences = [(theirs, mine) for theirs, mine in zip(reference, ours)
                   if theirs != mine]
    assert differences == []


@pytest.mark.parametrize('case', CASES, ids=IDS)
def test_the_comparison_is_not_made_of_errors(reference_traces, case):
    raising = [line for line in reference_traces[case] if ' raises ' in line]
    assert len(raising) == CASES[case]
    assert len(reference_traces[case]) - len(raising) > 0


def test_the_elevation_mode_changes_the_reference(reference_traces):
    """Control: los dos modos difieren en la referencia, o el modo no mide."""
    changed = [line for line, other in zip(
        reference_traces[('ir.rule', 'user', None)],
        reference_traces[('ir.rule', 'su', None)]) if line != other]
    assert changed
    assert all("'any'" in line or "'not any'" in line for line in changed)


def test_the_time_zone_changes_the_reference(reference_traces):
    """Control: el huso cambia la conversión de fechas a fecha-hora."""
    changed = [line for line, other in zip(
        reference_traces[('ir.cron', 'user', UTC)],
        reference_traces[('ir.cron', 'user', MEXICO)]) if line != other]
    assert changed
