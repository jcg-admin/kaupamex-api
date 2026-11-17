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


# --- Addons y anterioridad (instrucción 4.3.3 §8) -------------------------
# Diseño: scripts/workbench/orm-continuation-plan-20261103T095630/designs/
# reference-flow-gate-addons.md. Las citas son de la referencia real.

ACCOUNT = 'addons/account/models/account_payment_method.py'
BASE = 'src/addons/base/models/res_partner.py'
UNLINK = '≙ ``AccountPaymentMethod.unlink`` (``:90``)'
FIELD_CITE = 'odoo19c: addons/account/models/account_payment_method.py:104-109'
MODEL_OLD = ('class Line(models.Model):\n'
             "    payment_method = fields.Many2one('m', "
             'on_delete=models.CASCADE)\n\n'
             '    def unlink(self):\n        return 1\n')
MODEL_FIELD = MODEL_OLD.replace('CASCADE', 'PROTECT')
MODEL_BODY = MODEL_OLD.replace('return 1', 'return 2')


@pytest.mark.parametrize('path, text, accepted', [
    (ACCOUNT, UNLINK, True),
    (ACCOUNT, '≙ ``AccountPaymentMethod.unlink`` (``:20``)', False),
    (BASE, '≙ ``ResPartner._check_parent_id`` (``:547``)', True),
    (BASE, '≙ ``ResPartner._check_parent_id`` (``:10``)', False),
])
def test_an_addon_citation_resolves_against_its_mirror(path, text,
                                                       accepted):
    assert (gate.citation_problems(path, '', text) == []) is accepted


@pytest.mark.parametrize('path, kind', [
    ('src/orm/fields.py', 'A'),
    (ACCOUNT, 'B'),
    (BASE, 'B'),
    ('addons/account/migrations/0041_x.py', 'C'),
    ('addons/kaupamex_only/models/plan.py', 'E'),
    ('addons/account/controllers/main.py', None),
])
def test_each_path_has_its_change_kind(path, kind):
    assert gate.change_kind(path) == kind


def test_an_addon_method_change_without_design_is_rejected():
    problems = gate.flow_problems(ACCOUNT, MODEL_OLD, MODEL_BODY, {})
    assert problems and 'Line.unlink cambia' in problems[0]


def test_an_addon_field_change_without_design_is_rejected():
    problems = gate.flow_problems(ACCOUNT, MODEL_OLD, MODEL_FIELD, {})
    assert problems and 'Line.payment_method cambia' in problems[0]


def test_an_addon_field_change_with_prior_design_is_admitted():
    design = f'`payment_method` restrict, {FIELD_CITE}; prueba: {TEST}'
    assert gate.flow_problems(ACCOUNT, MODEL_OLD, MODEL_FIELD,
                              {'d.md': design}) == []


def test_an_addon_docstring_only_change_needs_nothing():
    old = 'class Line:\n    def f(self):\n        """A."""\n        return 1\n'
    assert gate.flow_problems(ACCOUNT, old, old.replace('A.', 'B.'),
                              {}) == []


def test_a_new_migration_without_design_is_rejected():
    path = 'addons/account/migrations/0041_restrict_x.py'
    assert gate.flow_problems(path, None, 'x = 1\n', {})


def test_a_new_migration_named_by_a_prior_design_is_admitted():
    path = 'addons/account/migrations/0041_restrict_x.py'
    design = f'Migración `0041_restrict_x`: {FIELD_CITE}; prueba: {TEST}'
    assert gate.flow_problems(path, None, 'x = 1\n',
                              {'d.md': design}) == []


def test_an_edited_migration_is_not_judged_again():
    path = 'addons/account/migrations/0041_restrict_x.py'
    assert gate.flow_problems(path, 'x = 1\n', 'x = 2\n', {}) == []


def test_an_unmirrored_model_needs_a_design_but_no_citation():
    path = 'addons/kaupamex_only/models/plan.py'
    assert gate.flow_problems(path, MODEL_OLD, MODEL_BODY, {})
    design = f'`unlink` propio del L0, sin contraparte; prueba: {TEST}'
    assert gate.flow_problems(path, MODEL_OLD, MODEL_BODY,
                              {'d.md': design}) == []


def test_a_design_only_in_the_index_does_not_precede_the_change():
    design = f'`unlink` sigue {UNLINK}; prueba: {TEST}'
    problems = gate.flow_problems(ACCOUNT, MODEL_OLD, MODEL_BODY, {},
                                  staged_designs={'d.md': design})
    assert problems and 'no precede' in problems[0]


def test_a_prior_design_reused_unchanged_admits_the_change():
    design = f'`unlink` sigue {UNLINK}; prueba: {TEST}'
    assert gate.flow_problems(ACCOUNT, MODEL_OLD, MODEL_BODY,
                              {'d.md': design},
                              staged_designs={'d.md': design}) == []


@pytest.mark.parametrize('path, measured', [
    ('src/orm/models.py', True),
    (ACCOUNT, True),
    ('addons/account/migrations/0041_x.py', True),
    ('addons/account/controllers/main.py', False),
    ('scripts/check_reference_flow.py', False),
])
def test_the_scope_covers_orm_models_and_migrations(path, measured):
    assert gate.in_scope(path) is measured


@pytest.mark.parametrize('path, text, accepted', [
    (ACCOUNT, 'odoo19c: account_payment_method.py:90-92', True),
    (ACCOUNT, 'odoo19c: account_payment_method.py:999999', False),
    (ACCOUNT, 'odoo19c: no_such_model.py:1', False),
])
def test_a_short_path_citation_resolves_in_the_mirror_package(path, text,
                                                              accepted):
    assert (gate.citation_problems(path, '', text) == []) is accepted
