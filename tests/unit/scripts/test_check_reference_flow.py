"""El gate de flujo de referencia rechaza lo inventado y admite lo fiel.

``scripts/check_reference_flow.py`` (instrucción 4.3.2 §6). Los positivos de
rechazo son citas REALES del árbol que no resuelven —``env.registry
(:172)`` apunta a un cuerpo ajeno de ``environments.py``—, no inventadas
por la prueba.
"""
import importlib.util
import pathlib
import sys

import pytest

_PATH = pathlib.Path(__file__).resolve().parents[3] / 'scripts' / (
    'check_reference_flow.py')
_spec = importlib.util.spec_from_file_location('check_reference_flow', _PATH)
gate = importlib.util.module_from_spec(_spec)
sys.modules['check_reference_flow'] = gate
_spec.loader.exec_module(gate)

pytestmark = pytest.mark.skipif(
    not (gate.REFERENCE / 'odoo' / 'orm').is_dir(),
    reason='requiere odoo-tools')

FAITHFUL = '≙ ``Field.__get__`` (``:1642``)'
MISPLACED = '≙ ``env.registry`` (``:172``)'


def test_a_citation_to_the_cited_definition_resolves():
    assert gate.citation_problems('src/orm/fields.py', '', FAITHFUL) == []


def test_a_real_citation_into_an_unrelated_body_is_rejected():
    problems = gate.citation_problems('src/orm/environments.py', '',
                                      MISPLACED)
    assert len(problems) == 1 and 'registry' in problems[0]


def test_a_definition_in_another_file_of_the_package_resolves():
    """``_search_related`` vive en ``fields.py``; la cita sale de
    ``domains.py``."""
    text = '≙ ``Field._search_related`` (``:735``)'
    assert gate.citation_problems('src/orm/domains.py', '', text) == []


def test_a_symbol_the_reference_does_not_have_is_rejected():
    text = '≙ ``Environment.transaction_scope`` (``:100``)'
    assert gate.citation_problems('src/orm/environments.py', '', text)


@pytest.mark.parametrize('text, accepted', [
    ('odoo19c: odoo/orm/fields.py:1807-1847', True),
    ('odoo19c: odoo/orm/no_such_file.py:10', False),
    ('odoo19c: odoo/orm/fields.py:999999', False),
])
def test_a_path_citation_must_exist_and_fit(text, accepted):
    problems = gate.citation_problems('src/orm/fields.py', '', text)
    assert (problems == []) is accepted


def test_an_inherited_citation_is_not_judged():
    """La deuda de ``HEAD`` se paga al tocarla, no al pasar al lado."""
    assert gate.citation_problems('src/orm/environments.py', MISPLACED,
                                  MISPLACED + '\n') == []


OLD = 'def f(x):\n    """Doc."""\n    return x\n'
NEW_BODY = 'def f(x):\n    """Doc."""\n    return x + 1\n'
NEW_DOC = 'def f(x):\n    """Otro doc."""\n    return x\n'
TEST = 'tests/unit/scripts/test_check_reference_flow.py'


def test_a_docstring_change_needs_no_design():
    assert gate.flow_problems('src/orm/fields.py', OLD, NEW_DOC, {}) == []


def test_a_body_change_without_design_is_rejected():
    problems = gate.flow_problems('src/orm/fields.py', OLD, NEW_BODY, {})
    assert problems and 'f cambia' in problems[0]


def test_a_design_that_names_cites_and_tests_admits_it():
    design = f'`f` sigue {FAITHFUL}; prueba: {TEST}'
    assert gate.flow_problems('src/orm/fields.py', OLD, NEW_BODY,
                              {'d.md': design}) == []


@pytest.mark.parametrize('design', [
    f'`f` sigue {FAITHFUL}; sin prueba nombrada',
    f'`f` sigue {MISPLACED}; prueba: {TEST}',
    f'otra función, {FAITHFUL}; prueba: {TEST}',
])
def test_an_incomplete_design_does_not_admit_it(design):
    assert gate.flow_problems('src/orm/environments.py', OLD, NEW_BODY,
                              {'d.md': design})


def test_without_the_reference_it_refuses_to_count(tmp_path, capsys):
    assert gate.main(['--reference', str(tmp_path)]) == 2
    assert 'no se emite conteo' in capsys.readouterr().err
