"""El gate revisa todo el índice y falla cerrado ante formato o imports."""
import os
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / 'scripts' / 'check_python_style.sh'


def run_gate(repository, mode):
    """Invoca la interfaz real sin conectar con Django ni PostgreSQL."""
    return subprocess.run(
        ['bash', str(GATE), mode],
        cwd=repository,
        env=dict(os.environ),
        text=True,
        capture_output=True,
    )


@pytest.fixture
def repository(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    return tmp_path


@pytest.mark.parametrize('source', [
    'answer=42\n',
    'answer = 42\n\nimport os\n',
    'class Example:\n    import os\n',
])
def test_complete_gate_rejects_bad_format_or_misplaced_imports(
    repository, source,
):
    path = repository / 'example.py'
    path.write_text(source)
    subprocess.run(['git', 'add', path.name], cwd=repository, check=True)
    result = run_gate(repository, '--all')
    assert result.returncode == 1, result.stdout + result.stderr


def test_staged_gate_checks_index_instead_of_unstaged_fix(repository):
    path = repository / 'example.py'
    path.write_text('answer=42\n')
    subprocess.run(['git', 'add', path.name], cwd=repository, check=True)
    path.write_text('answer = 42\n')
    result = run_gate(repository, '--staged')
    assert result.returncode == 1, result.stdout + result.stderr


def test_staged_gate_does_not_test_unstaged_breakage(repository):
    path = repository / 'example.py'
    path.write_text('answer = 42\n')
    subprocess.run(['git', 'add', path.name], cwd=repository, check=True)
    path.write_text('answer=42\n')
    result = run_gate(repository, '--staged')
    assert result.returncode == 0, result.stdout + result.stderr


def test_empty_repository_cannot_report_success(repository):
    result = run_gate(repository, '--all')
    assert result.returncode == 2


@pytest.mark.parametrize('source', [
    '#!/usr/bin/env python3\nanswer=42\n',
    '#!/usr/bin/env python3\nanswer = 42\n\nimport os\n',
    '#!/usr/bin/env python3\nclass Example:\n    import os\n',
    '#!/usr/bin/env python3\nreturn 42\n',
])
def test_gate_rejects_extensionless_python(repository, source):
    path = repository / 'application'
    path.write_text(source)
    path.chmod(0o755)
    subprocess.run(['git', 'add', path.name], cwd=repository, check=True)
    result = run_gate(repository, '--all')
    assert result.returncode == 1, result.stdout + result.stderr


def test_extensionless_python_uses_staged_content(repository):
    path = repository / 'application'
    path.write_text('#!/usr/bin/env python3\nanswer=42\n')
    path.chmod(0o755)
    subprocess.run(['git', 'add', path.name], cwd=repository, check=True)
    path.write_text('#!/bin/sh\necho corrected\n')
    result = run_gate(repository, '--staged')
    assert result.returncode == 1, result.stdout + result.stderr


def test_gate_checks_untracked_python_executable(repository):
    path = repository / 'application'
    path.write_text('#!/usr/bin/env python3\nanswer=42\n')
    path.chmod(0o755)
    result = run_gate(repository, '--all')
    assert result.returncode == 1, result.stdout + result.stderr


def test_gate_does_not_parse_shell_as_python(repository):
    (repository / 'example.py').write_text('answer = 42\n')
    path = repository / 'application'
    path.write_text('#!/bin/sh\necho "not Python"\n')
    path.chmod(0o755)
    result = run_gate(repository, '--all')
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize('shebang', [
    '#!/usr/bin/python3',
    '#!/usr/bin/env -S python3 -u',
])
def test_valid_python_executable_is_verified(repository, shebang):
    path = repository / 'application'
    path.write_text(f'{shebang}\nanswer = 42\n')
    path.chmod(0o755)
    subprocess.run(['git', 'add', path.name], cwd=repository, check=True)
    result = run_gate(repository, '--staged')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS (1 sources;' in result.stdout
