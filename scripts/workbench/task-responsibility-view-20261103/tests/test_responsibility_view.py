"""Control de la vista de responsabilidad: los ejes no se derivan unos de otros."""
import pathlib
import sqlite3
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import responsibility_view as view  # noqa: E402

PROSE = ('TASK-API-0001 conserva owner x; responsabilidad funcional devops, '
         'verificación qa. TASK-API-0002 sigue abierta. TASK-THYROX-0003 es '
         'del proveedor. TASK-GEN-0004 se mudó.\n\n'
         '.. list-table::\n\n   * - backend\n     - 1 (TASK-API-0002)\n'
         '   * - devops\n     - 1 (TASK-API-0001, verificación qa)\n')


def _fixture(tmp_path):
    initiative = tmp_path / 'ini'
    initiative.mkdir()
    (initiative / 'progreso.rst').write_text(PROSE)
    store = tmp_path / 'store.sqlite3'
    connection = sqlite3.connect(store)
    connection.execute('create table tasks (citation_id, layer_citation_id, subject, '
                       'status, owner, session_id, blocked_by_json)')
    connection.executemany('insert into tasks values (?,?,?,?,?,?,?)', [
        ('TASK-API-0001', None, 'Portar el gate de CI', 'pending', 'ci', 's1', '[]'),
        ('TASK-API-0002', None, 'Portar el campo', 'pending', None, 's1', '[]'),
        ('TASK-GEN-0004', 'TASK-THYROX-0009', 'Mover', 'pending', None, 's2', '[]'),
    ])
    connection.commit()
    return view.build(initiative, store, [], [])


def test_role_and_verifier_are_read_from_one_sentence(tmp_path):
    rows, _ = _fixture(tmp_path)
    first = next(r for r in rows if r['citation'] == 'TASK-API-0001')
    assert (first['functional_role'], first['verifier']) == ('devops', 'qa')


def test_an_undeclared_role_is_not_verified_and_a_null_owner_is_unassigned(tmp_path):
    rows, _ = _fixture(tmp_path)
    second = next(r for r in rows if r['citation'] == 'TASK-API-0002')
    assert second['functional_role'] == 'not_verified'
    assert second['proposed_role'] == 'backend (inferido)'
    assert second['operational_owner'] == 'unassigned'


def test_provider_tasks_are_excluded(tmp_path):
    rows, excluded = _fixture(tmp_path)
    assert sorted(excluded) == ['TASK-GEN-0004', 'TASK-THYROX-0003']
    assert {r['citation'] for r in rows} == {'TASK-API-0001', 'TASK-API-0002'}


def test_a_table_row_does_not_lend_its_verifier_to_the_neighbour_row(tmp_path):
    rows, _ = _fixture(tmp_path)
    second = next(r for r in rows if r['citation'] == 'TASK-API-0002')
    assert second['verifier'] == 'not_verified'
