"""Admisión explícita sin modificar los contratos globales de estilo."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / 'scripts/check_python_style.sh'
DEBT = "historical_note = '" + 'a' * 90 + "'\n"


def git(repo, *args):
    """Git real aislado, sin cambiar configuración de los checkouts activos."""
    env = dict(
        os.environ,
        GIT_AUTHOR_NAME='Style qualification fixture',
        GIT_AUTHOR_EMAIL='style@example.invalid',
        GIT_COMMITTER_NAME='Style qualification fixture',
        GIT_COMMITTER_EMAIL='style@example.invalid',
    )
    return subprocess.check_output(
        ['git', *args], cwd=repo, env=env, text=True,
    ).strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, 'init', '-q')
    (tmp_path / 'sample.py').write_text(DEBT)
    git(tmp_path, 'add', '.')
    git(tmp_path, 'commit', '-qm', 'Base fixture')
    return tmp_path


def admit(repo, base=None, candidate=None, expected_tree=None, qualify=False):
    """Interfaz pública y evidencia JSON reales, nunca un gate simulado."""
    report = repo / 'admission.json'
    args = ['--base', base or git(repo, 'rev-parse', 'HEAD')]
    if candidate:
        args += ['--candidate', candidate]
    else:
        args += ['--index-tree', expected_tree or git(repo, 'write-tree')]
    if qualify:
        args += ['--qualify-checkers']
    result = subprocess.run(
        ['bash', str(GATE), '--increment', *args, '--report', str(report)],
        cwd=repo, text=True, capture_output=True,
        env=dict(os.environ, UV_OFFLINE='1'),
    )
    assert report.exists(), result.stdout + result.stderr
    return result, json.loads(report.read_text())


def stage(repo, text, name='sample.py'):
    (repo / name).write_text(text)
    git(repo, 'add', name)


def test_inherited_debt_is_not_global_pass(repo):
    stage(repo, DEBT + 'translated = True\n')
    result, report = admit(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert report['increment_admission'] == 'PASS'
    assert report['global_style_compliance'] == 'NOT_EVALUATED'
    assert report['files'][0]['inherited']
    assert report['files'][0]['candidate_checks']['style_exit'] == 1
    assert report['ci_verification'] == 'NOT_EVALUATED'
    assert report['acceptance'] == 'NOT_EVALUATED'


@pytest.mark.parametrize('source', [
    DEBT + 'answer=42\n',
    "historical_note = 'fixed'\nnew_note = '" + 'b' * 100 + "'\n",
    DEBT + '\n\ndef example():\n    import os\n    return os\n',
    DEBT + 'def broken(:\n',
    DEBT + 'return 42\n',
    DEBT + "invalid_escape = '\\q'\n",
])
def test_regressions_are_rejected_including_equal_counts(repo, source):
    stage(repo, source)
    result, report = admit(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert report['increment_admission'] == 'FAIL'


def test_old_error_can_be_corrected(repo):
    stage(repo, "historical_note = 'fixed'\n")
    result, report = admit(repo)
    assert result.returncode == 0
    assert report['files'][0]['corrected']


def test_new_file_cannot_inherit_an_old_identical_diagnostic(repo):
    stage(repo, DEBT, 'new.py')
    result, _ = admit(repo)
    assert result.returncode == 1


def test_clean_new_file_is_admitted(repo):
    stage(repo, 'answer = 42\n', 'new.py')
    result, _ = admit(repo)
    assert result.returncode == 0


@pytest.mark.parametrize('clean', [True, False])
def test_exact_rename_requires_strict_candidate_conformity(repo, clean):
    if clean:
        stage(repo, 'answer = 42\n')
        git(repo, 'commit', '-qm', 'Clean fixture')
    git(repo, 'mv', 'sample.py', 'renamed.py')
    result, report = admit(repo)
    assert result.returncode == (0 if clean else 1)
    assert report['files'][0]['status'].startswith('R')


def test_deleted_file_is_recorded_not_silently_ignored(repo):
    git(repo, 'rm', '-q', 'sample.py')
    result, report = admit(repo)
    assert result.returncode == 0
    assert report['files'][0]['status'] == 'D'


def test_context_change_cannot_grandfather_the_same_physical_line(repo):
    stage(repo, 'if True:\n    ' + DEBT)
    result, _ = admit(repo)
    assert result.returncode == 1


def test_unchanged_line_with_changed_enclosing_header_is_not_inherited(repo):
    original = 'class Original:\n    ' + DEBT
    stage(repo, original)
    git(repo, 'commit', '-qm', 'Class fixture')
    stage(repo, original.replace('Original', 'Different'))
    result, _ = admit(repo)
    assert result.returncode == 1


def test_only_index_content_is_evaluated(repo):
    stage(repo, DEBT + 'answer = 42\n')
    (repo / 'sample.py').write_text('answer=42\n')
    result, _ = admit(repo)
    assert result.returncode == 0


def test_wrong_index_tree_fails_closed(repo):
    old = git(repo, 'write-tree')
    stage(repo, DEBT + 'answer = 42\n')
    result, report = admit(repo, expected_tree=old)
    assert result.returncode == 2
    assert report['increment_admission'] == 'ERROR'


def test_symbolic_or_missing_base_is_not_a_concrete_revision(repo):
    stage(repo, DEBT + 'answer = 42\n')
    for base in ['HEAD', 'f' * 40]:
        result, _ = admit(repo, base=base)
        assert result.returncode == 2


def test_stale_base_for_index_is_refused(repo):
    old = git(repo, 'rev-parse', 'HEAD')
    stage(repo, DEBT + 'answer = 42\n')
    git(repo, 'commit', '-qm', 'New head fixture')
    stage(repo, DEBT + 'answer = 43\n')
    result, _ = admit(repo, base=old)
    assert result.returncode == 2


def test_commit_revision_candidate_is_supported(repo):
    base = git(repo, 'rev-parse', 'HEAD')
    stage(repo, DEBT + 'answer = 42\n')
    git(repo, 'commit', '-qm', 'Candidate fixture')
    candidate = git(repo, 'rev-parse', 'HEAD')
    result, report = admit(repo, base=base, candidate=candidate)
    assert result.returncode == 0
    assert report['candidate']['revision'] == candidate


def test_empty_python_scope_cannot_report_admission(repo):
    result, _ = admit(repo)
    assert result.returncode == 2


def test_new_suppression_is_not_a_fix(repo):
    stage(repo, DEBT.rstrip() + '  # noqa\n')
    result, _ = admit(repo)
    assert result.returncode == 2


def test_removing_an_old_suppression_does_not_hide_base_debt(repo):
    stage(repo, DEBT.rstrip() + '  # noqa\n')
    git(repo, 'commit', '-qm', 'Suppressed baseline fixture')
    stage(repo, "historical_note = 'fixed'\n")
    result, report = admit(repo)
    assert result.returncode == 0
    assert report['files'][0]['corrected']


def test_unchanged_old_suppression_cannot_hide_style_debt(repo):
    suppressed = DEBT.rstrip() + '  # noqa: BLE001\n'
    stage(repo, suppressed)
    git(repo, 'commit', '-qm', 'Suppression provenance fixture')
    stage(repo, suppressed + 'answer = 42\n')
    result, report = admit(repo)
    assert result.returncode == 0
    file = report['files'][0]
    assert file['candidate_checks']['style_exit'] == 1
    assert any(row['code'] == 'E501' for row in file['inherited'])
    assert any(row['code'] == 'SUPPRESSION' for row in file['inherited'])


def test_changed_old_suppression_is_rejected(repo):
    suppressed = DEBT.rstrip() + '  # noqa: BLE001\n'
    stage(repo, suppressed)
    git(repo, 'commit', '-qm', 'Suppression fixture')
    stage(repo, suppressed.replace('BLE001', 'E501'))
    result, _ = admit(repo)
    assert result.returncode == 2


def test_moved_old_suppression_is_rejected(repo):
    suppressed = DEBT.rstrip() + '  # noqa: BLE001\n'
    stage(repo, suppressed)
    git(repo, 'commit', '-qm', 'Suppression fixture')
    stage(repo, 'answer = 42\n' + suppressed)
    result, _ = admit(repo)
    assert result.returncode == 2


def test_policy_change_requires_separate_qualification(repo):
    stage(repo, DEBT + 'answer = 42\n')
    stage(repo, '[tool.example]\n', 'pyproject.toml')
    result, _ = admit(repo)
    assert result.returncode == 2


@pytest.mark.parametrize('valid', [True, False])
def test_extensionless_executables_are_not_omitted(repo, valid):
    path = repo / 'application'
    path.write_text(
        '#!/usr/bin/env python3\n' + ('answer = 42\n' if valid else DEBT)
    )
    path.chmod(0o755)
    git(repo, 'add', 'application')
    result, _ = admit(repo)
    assert result.returncode == (0 if valid else 1)


def test_python_classification_cannot_be_removed_to_hide_debt(repo):
    path = repo / 'application'
    path.write_text('#!/usr/bin/env python3\n' + DEBT)
    path.chmod(0o755)
    git(repo, 'add', 'application')
    git(repo, 'commit', '-qm', 'Executable fixture')
    path.chmod(0o644)
    git(repo, 'add', 'application')
    result, _ = admit(repo)
    assert result.returncode == 2


def test_python_symlink_is_not_followed(repo):
    (repo / 'linked.py').symlink_to('/etc/passwd')
    git(repo, 'add', 'linked.py')
    result, _ = admit(repo)
    assert result.returncode == 2


def test_duplicate_diagnostics_do_not_hide_an_added_occurrence(repo):
    stage(repo, DEBT * 2)
    git(repo, 'commit', '-qm', 'Repeated debt fixture')
    stage(repo, DEBT * 3)
    result, report = admit(repo)
    assert result.returncode == 1
    assert report['files'][0]['introduced']


def test_changed_logical_string_context_is_not_a_correction(repo):
    source = '"""' + 'long phrase ' * 12 + '\noriginal description\n"""\n'
    stage(repo, source)
    git(repo, 'commit', '-qm', 'Docstring fixture')
    stage(repo, source.replace('original', 'different'))
    result, report = admit(repo)
    assert result.returncode == 1
    assert report['files'][0]['invalidated_context']
    assert not report['files'][0]['corrected']


def test_new_late_module_import_is_rejected(repo):
    stage(repo, DEBT + '\nimport os\n')
    result, report = admit(repo)
    assert result.returncode == 1
    assert any(
        row['code'] == 'IMPORT'
        for row in report['files'][0]['introduced']
    )


def test_invalid_base_is_not_treated_as_empty_debt(repo):
    stage(repo, 'def broken(:\n')
    git(repo, 'commit', '-qm', 'Invalid baseline fixture')
    stage(repo, 'answer = 42\n')
    result, _ = admit(repo)
    assert result.returncode == 2


def test_unrelated_candidate_revision_is_refused(repo):
    base = git(repo, 'rev-parse', 'HEAD')
    git(repo, 'checkout', '--orphan', 'unrelated', '-q')
    stage(repo, 'answer = 42\n')
    git(repo, 'commit', '-qm', 'Unrelated fixture')
    candidate = git(repo, 'rev-parse', 'HEAD')
    result, _ = admit(repo, base=base, candidate=candidate)
    assert result.returncode == 2


def test_changed_index_during_verification_fails_closed(repo, monkeypatch):
    stage(repo, DEBT + 'answer = 42\n')
    expected = git(repo, 'write-tree')
    actual_git = shutil.which('git')
    shim = repo / 'shim'
    shim.mkdir()
    counter = repo / 'calls'
    (repo / 'surprise.py').write_text('answer = 43\n')
    executable = shim / 'git'
    executable.write_text(
        f'#!{sys.executable}\n'
        'from pathlib import Path\nimport subprocess\nimport sys\n'
        f'counter = Path({str(counter)!r})\n'
        'if sys.argv[1:] == ["write-tree"]:\n'
        '    count = int(counter.read_text()) if counter.exists() else 0\n'
        '    counter.write_text(str(count + 1))\n'
        '    if count == 1:\n'
        f'        subprocess.run([{actual_git!r}, "add", "surprise.py"],'
        ' check=True)\n'
        f'result = subprocess.run([{actual_git!r}, *sys.argv[1:]])\n'
        'sys.exit(result.returncode)\n'
    )
    executable.chmod(0o755)
    monkeypatch.setenv('PATH', f'{shim}:{os.environ["PATH"]}')
    result, report = admit(repo, expected_tree=expected)
    assert result.returncode == 2
    assert any('changed during' in item for item in report['reasons'])


@pytest.mark.parametrize('global_clean', [True, False])
def test_global_mode_remains_strict_after_hook_activation(repo, global_clean):
    source = 'answer = 42\n' if global_clean else DEBT + 'answer = 42\n'
    stage(repo, source)
    incremental, _ = admit(repo)
    assert incremental.returncode == 0
    result = subprocess.run(
        ['bash', str(GATE), '--staged'],
        cwd=repo, capture_output=True, text=True,
        env=dict(os.environ, UV_OFFLINE='1'),
    )
    assert result.returncode == (0 if global_clean else 1), (
        result.stdout + result.stderr
    )


def actual_hook(repo):
    """Invoca el hook real y comprueba otro verificador conservado."""
    scripts = repo / 'scripts'
    scripts.mkdir(exist_ok=True)
    (scripts / 'check_python_style.sh').write_text(
        '#!/bin/bash\nexec bash ' + repr(str(GATE)) + ' "$@"\n'
    )
    (scripts / 'check_catalog_declaration.py').write_text(
        "from pathlib import Path\n"
        "Path('other-gate-ran').write_text('yes')\n"
    )
    hook = repo / 'pre-commit-fixture'
    hook.write_bytes((ROOT / '.githooks/pre-commit').read_bytes())
    result = subprocess.run(
        ['bash', str(hook)], cwd=repo, capture_output=True, text=True,
        env=dict(os.environ, UV_OFFLINE='1'),
    )
    assert (repo / 'other-gate-ran').exists(), result.stdout + result.stderr
    return result


@pytest.mark.parametrize('text,expected', [
    (DEBT + 'answer = 42\n', 0),
    (DEBT + 'answer=42\n', 1),
    (DEBT + '\nimport os\n', 1),
    ('if True:\n    ' + DEBT, 1),
], ids=['clean', 'style', 'imports', 'context'])
def test_real_hook_rejects_regressions_and_preserves_other_gates(
    repo, text, expected,
):
    stage(repo, text)
    result = actual_hook(repo)
    assert result.returncode == expected, result.stdout + result.stderr
    report = json.loads((repo / 'scripts/evidence/'
                         'ci-local-fail-fast-20261022T004947/outputs/'
                         'pre-commit-admission.json').read_text())
    assert report['global_style_compliance'] == 'NOT_EVALUATED'
    assert report['exit_code'] == expected


def test_real_hook_rejects_invalid_provenance(repo, monkeypatch):
    stage(repo, DEBT + 'answer = 42\n')
    actual_git = shutil.which('git')
    shim = repo / 'shim'
    shim.mkdir()
    executable = shim / 'git'
    executable.write_text(
        f'#!{sys.executable}\nimport subprocess\nimport sys\n'
        'if sys.argv[1:] == ["rev-parse", "--verify", "HEAD"]:\n'
        '    print("f" * 40)\n    sys.exit(0)\n'
        f'result = subprocess.run([{actual_git!r}, *sys.argv[1:]])\n'
        'sys.exit(result.returncode)\n'
    )
    executable.chmod(0o755)
    monkeypatch.setenv('PATH', f'{shim}:{os.environ["PATH"]}')
    result = actual_hook(repo)
    assert result.returncode == 1
    assert 'ERROR' in result.stdout
    report_path = (
        repo / 'scripts/evidence/ci-local-fail-fast-20261022T004947'
        / 'outputs/pre-commit-admission.json'
    )
    report = json.loads(report_path.read_text())
    assert report['increment_admission'] == 'ERROR'
    assert report['exit_code'] == 2
    assert report['reasons']
    assert report['global_style_compliance'] == 'NOT_EVALUATED'


def test_qualification_flag_is_not_a_policy_bypass(repo):
    stage(repo, DEBT + 'answer = 42\n')
    stage(repo, '[tool.example]\n', 'pyproject.toml')
    result, _ = admit(repo, qualify=True)
    assert result.returncode == 2


@pytest.mark.parametrize('source,expected', [
    ("literal = '# noqa'\n", 0),
    ("literal = '" + 'long phrase ' * 12 + "# noqa'\n", 1),
])
def test_fixture_strings_cannot_suppress_native_diagnostics(
    repo, source, expected,
):
    stage(repo, source, 'fixture.py')
    result, _ = admit(repo)
    assert result.returncode == expected


def test_evidence_is_not_reused_when_verifier_changes(repo, monkeypatch):
    stage(repo, DEBT + 'answer = 42\n')
    expected = git(repo, 'write-tree')
    base = git(repo, 'rev-parse', 'HEAD')
    actual_git = shutil.which('git')
    copies = repo / 'verifiers'
    copies.mkdir()
    for name in [
        'check_python_style_increment.py', 'check_no_lazy_imports.py',
    ]:
        shutil.copyfile(ROOT / 'scripts' / name, copies / name)
    counter = repo / 'calls'
    shim = repo / 'shim'
    shim.mkdir()
    changed = copies / 'check_no_lazy_imports.py'
    executable = shim / 'git'
    executable.write_text(
        f'#!{sys.executable}\n'
        'from pathlib import Path\nimport subprocess\nimport sys\n'
        f'counter = Path({str(counter)!r})\n'
        'if sys.argv[1:] == ["write-tree"]:\n'
        '    count = int(counter.read_text()) if counter.exists() else 0\n'
        '    counter.write_text(str(count + 1))\n'
        '    if count == 1:\n'
        f'        changed = Path({str(changed)!r})\n'
        '        changed.write_text(changed.read_text() + "\\n# changed\\n")\n'
        f'result = subprocess.run([{actual_git!r}, *sys.argv[1:]])\n'
        'sys.exit(result.returncode)\n'
    )
    executable.chmod(0o755)
    monkeypatch.setenv('PATH', f'{shim}:{os.environ["PATH"]}')
    report = repo / 'provenance.json'
    result = subprocess.run(
        [
            sys.executable, str(copies / 'check_python_style_increment.py'),
            '--base', base, '--index-tree', expected, '--report', str(report),
        ], cwd=repo, capture_output=True, text=True,
    )
    assert result.returncode == 2, result.stdout + result.stderr
    assert any(
        'Verifier changed' in reason
        for reason in json.loads(report.read_text())['reasons']
    )
