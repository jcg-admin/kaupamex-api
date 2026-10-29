"""Compara estilo de un incremento explícito; no activa hooks ni acepta código.

Reutiliza pycodestyle y el checker de imports del Consumer sobre blobs Git.
Exit0 admite sólo el incremento; exit1 rechaza infracciones; exit2 rehúsa una
comparación incompleta o no fiable. Ninguna salida acredita conformidad global.
"""
import argparse
import ast
from collections import Counter
import difflib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tokenize
import warnings
import xml.etree.ElementTree as ET

import pycodestyle

from check_no_lazy_imports import find_misplaced_imports


PROTECTED = {
    'pyproject.toml', 'uv.lock', 'setup.cfg', 'tox.ini', '.pep8',
    '.pycodestyle', 'Makefile', 'AGENTS.md', 'docs/python-style.md',
    'scripts/check_python_style.sh',
    'scripts/check_python_style_increment.py',
    'scripts/check_no_lazy_imports.py',
}
SHA = re.compile(r'[0-9a-f]{40}\Z')
SHEBANG = re.compile(
    rb'^#!.*[/\s]python(?:\d+(?:\.\d+)*)?(?:\s|$)',
)
BODY_FIELDS = {'body', 'orelse', 'finalbody', 'handlers', 'cases'}
QUALIFICATION_TESTS = [
    'tests/unit/scripts/test_python_style_increment.py',
    'tests/unit/scripts/test_python_style_gate.py',
    'tests/unit/scripts/test_check_no_lazy_imports.py',
    'tests/unit/scripts/test_ci_verification.py',
]
QUALIFIED_SURFACES = {
    '.githooks/pre-commit', 'AGENTS.md', 'Makefile', 'pyproject.toml',
    'uv.lock', 'docs/python-style.md', 'scripts/check_python_style.sh',
    'scripts/check_python_style_increment.py',
    'scripts/check_no_lazy_imports.py', *QUALIFICATION_TESTS,
}


class Unverifiable(Exception):
    """La procedencia o el contexto no permiten emitir una admisión."""


class Diagnostics(pycodestyle.BaseReport):
    """Conserva sólo diagnósticos que el verificador nativo realmente emite."""

    def __init__(self, options):
        super().__init__(options)
        self.rows = []

    def error(self, line_number, offset, text, check):
        code = super().error(line_number, offset, text, check)
        if code:
            self.rows.append((line_number, offset + 1, code, text[5:]))
        return code


def git(*args):
    """No usa shell, alias, diffs externos ni código del candidato."""
    result = subprocess.run(
        ['git', *args], capture_output=True, check=False,
    )
    if result.returncode:
        raise Unverifiable(
            f'Git {args[0]} failed with exit {result.returncode}'
        )
    return result.stdout


def oid(value, kind):
    """No admite HEAD, abreviaturas o revisiones resolubles ambiguamente."""
    if not SHA.fullmatch(value):
        raise Unverifiable('A full lowercase SHA-1 is required')
    actual = git(
        'rev-parse', '--verify', f'{value}^{{{kind}}}',
    ).decode().strip()
    if actual != value:
        raise Unverifiable(f'The declared object is not a {kind}')
    return actual


def changes(base, candidate):
    """Renombres exactos son explícitos; renombres editados son baja y alta."""
    raw = git(
        'diff', '--raw', '--no-abbrev', '--no-ext-diff', '--no-textconv',
        '--find-renames=100%', '-z', base, candidate, '--',
    ).split(b'\0')
    rows = []
    index = 0
    while index < len(raw) and raw[index]:
        header = raw[index].decode('ascii').split()
        index += 1
        if len(header) != 5 or not header[0].startswith(':'):
            raise Unverifiable('Invalid Git raw-diff evidence')
        path = raw[index].decode('utf-8')
        index += 1
        status = header[4]
        old_path = path
        if status.startswith('R'):
            path = raw[index].decode('utf-8')
            index += 1
        if status[0] not in {'A', 'M', 'D', 'R', 'T'}:
            raise Unverifiable('Unsupported diff status')
        rows.append({
            'path': path, 'old_path': old_path, 'status': status,
            'old_mode': header[0][1:], 'new_mode': header[1],
            'old_blob': header[2], 'new_blob': header[3],
        })
    return rows


def blob(revision):
    size = int(git('cat-file', '-s', revision))
    if size > 4 * 1024 * 1024:
        raise Unverifiable('Source exceeds qualified size limit')
    return git('cat-file', 'blob', revision)


def python_source(path, mode, revision):
    if mode == '000000':
        return False
    if path.endswith('.py'):
        return True
    return mode == '100755' and bool(
        SHEBANG.match(blob(revision).split(b'\n', 1)[0])
    )


def syntax_context(tree, line):
    """Incluye unidad lógica, cabeceras, rama y posición en cada contenedor.

    No basta con que una línea física coincida: moverla de ámbito o cambiar
    su cabecera invalida la comparación. Contextos no demostrables se rehúsan.
    """
    parents = {}
    for parent in ast.walk(tree):
        for field, value in ast.iter_fields(parent):
            values = (
                enumerate(value) if isinstance(value, list) else [(0, value)]
            )
            for index, child in values:
                if isinstance(child, ast.AST):
                    parents[id(child)] = (parent, field, index)
    containing = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.stmt)
        and node.lineno <= line <= node.end_lineno
    ]
    node = min(
        containing, key=lambda item: item.end_lineno - item.lineno,
        default=tree,
    )
    context = [ast.dump(node, include_attributes=False)]
    context.append(line - getattr(node, 'lineno', 0))
    while id(node) in parents:
        parent, field, index = parents[id(node)]
        header = []
        for name, value in ast.iter_fields(parent):
            if name not in BODY_FIELDS:
                if isinstance(value, ast.AST):
                    value = ast.dump(value, include_attributes=False)
                elif isinstance(value, list):
                    value = [
                        ast.dump(item, include_attributes=False)
                        if isinstance(item, ast.AST) else item
                        for item in value
                    ]
                header.append((name, value))
        context.append((type(parent).__name__, field, index, header))
        node = parent
    return hashlib.sha256(json.dumps(context).encode()).hexdigest()


def inspect_source(raw, path, baseline=False):
    """Compila sin ejecutar; trata SyntaxWarning como error."""
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    text = raw.decode(encoding)
    if len(text.splitlines()) > 20000:
        raise Unverifiable('Source exceeds qualified line-count limit')
    with warnings.catch_warnings():
        warnings.simplefilter('error', SyntaxWarning)
        compile(raw, path, 'exec', dont_inherit=True)
        tree = ast.parse(raw, filename=path)
    pragma = re.compile(r'#\s*no(?:qa|pep8)\b', re.IGNORECASE)
    checked_lines = text.splitlines(keepends=True)
    offsets = [0]
    for value in checked_lines:
        offsets.append(offsets[-1] + len(value))
    replacements = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT and pragma.search(token.string):
            if not baseline:
                raise Unverifiable(
                    'Suppression in changed source requires review'
                )
        if token.type in {tokenize.STRING, tokenize.COMMENT} and pragma.search(
            token.string,
        ):
            # Un fixture puede contener la cadena, no una supresión real.
            # Se neutraliza conservando longitud para que el checker nativo
            # tampoco silencie E501 por encontrarla dentro de un literal.
            value = pragma.sub(lambda match: 'x' * len(match[0]), token.string)
            start = offsets[token.start[0] - 1] + token.start[1]
            end = offsets[token.end[0] - 1] + token.end[1]
            replacements.append((start, end, value))
    checked = text
    for start, end, value in reversed(replacements):
        checked = checked[:start] + value + checked[end:]
    # Defaults are explicit: no user/project config can weaken this comparison.
    parser = pycodestyle.get_parser()
    defaults, _ = parser.parse_args(['--ignore=W503'])
    options = vars(defaults)
    options['reporter'] = Diagnostics
    style = pycodestyle.StyleGuide(**options)
    native = style.options.report
    checker = pycodestyle.Checker(
        filename=path, lines=checked.splitlines(keepends=True),
        options=style.options,
    )
    checker.check_all()
    rows = list(native.rows)
    rows.extend(
        (line, 1, 'IMPORT', statement)
        for line, statement in find_misplaced_imports(tree)
    )
    diagnostics = []
    lines = text.splitlines()
    for line, column, code, message in rows:
        if not 1 <= line <= len(lines):
            raise Unverifiable('Diagnostic has no proven source line')
        fingerprint = hashlib.sha256(json.dumps([
            column, code, message, lines[line - 1], encoding,
            syntax_context(tree, line),
        ]).encode()).hexdigest()
        diagnostics.append({
            'line': line, 'column': column, 'code': code,
            'message': message, 'fingerprint': fingerprint,
        })
    return text.splitlines(), diagnostics


def evaluate_file(change):
    old_python = python_source(
        change['old_path'], change['old_mode'], change['old_blob'],
    )
    new_python = python_source(
        change['path'], change['new_mode'], change['new_blob'],
    )
    if not old_python and not new_python:
        return None
    result = dict(
        change, inherited=[], introduced=[], corrected=[],
        invalidated_context=[],
    )
    if change['status'] == 'D':
        result['decision'] = 'REMOVED'
        return result
    if not new_python:
        raise Unverifiable('Python classification was removed, not the file')
    if change['new_mode'] not in {'100644', '100755'}:
        raise Unverifiable('Python symlink or special file is not qualified')
    try:
        new_lines, new = inspect_source(
            blob(change['new_blob']), change['path'],
        )
    except (SyntaxError, SyntaxWarning) as error:
        result['introduced'] = [{
            'code': 'COMPILE', 'message': type(error).__name__,
            'line': getattr(error, 'lineno', None),
        }]
        result['decision'] = 'FAIL'
        result['candidate_checks'] = {
            'compilation_exit': 1, 'style': 'NOT_EVALUATED',
            'imports': 'NOT_EVALUATED',
        }
        return result
    result['candidate_checks'] = {
        'compilation_exit': 0,
        'style_exit': int(any(row['code'] != 'IMPORT' for row in new)),
        'imports_exit': int(any(row['code'] == 'IMPORT' for row in new)),
    }
    if change['status'].startswith(('A', 'R')) or not old_python:
        result['introduced'] = new
        result['decision'] = 'FAIL' if new else 'PASS'
        result['comparison'] = 'STRICT_NEW_OR_MOVED_FILE'
        return result
    if change['old_mode'] not in {'100644', '100755'}:
        raise Unverifiable('Base Python object is not a regular file')
    try:
        old_lines, old = inspect_source(
            blob(change['old_blob']), change['old_path'], baseline=True,
        )
    except (SyntaxError, SyntaxWarning) as error:
        raise Unverifiable('Base cannot be compiled reliably') from error
    result['base_checks'] = {
        'compilation_exit': 0,
        'style_exit': int(any(row['code'] != 'IMPORT' for row in old)),
        'imports_exit': int(any(row['code'] == 'IMPORT' for row in old)),
    }
    mapping = {}
    for tag, old_start, old_end, new_start, _ in difflib.SequenceMatcher(
        None, old_lines, new_lines, autojunk=False,
    ).get_opcodes():
        if tag == 'equal':
            for offset in range(old_end - old_start):
                mapping[new_start + offset + 1] = old_start + offset + 1
    available = Counter((row['line'], row['fingerprint']) for row in old)
    for row in new:
        key = (mapping.get(row['line']), row['fingerprint'])
        if available[key]:
            available[key] -= 1
            result['inherited'].append(row)
        else:
            result['introduced'].append(row)
    remaining = available.copy()
    forward = {old_line: new_line for new_line, old_line in mapping.items()}
    for row in old:
        key = (row['line'], row['fingerprint'])
        if remaining[key]:
            remaining[key] -= 1
            context_invalid = any(
                item['line'] == forward.get(row['line'])
                and item['code'] == row['code']
                for item in result['introduced']
            )
            key = 'invalidated_context' if context_invalid else 'corrected'
            result[key].append(row)
    result['decision'] = 'FAIL' if result['introduced'] else 'PASS'
    return result


def verifier_hashes():
    paths = [
        Path(__file__), Path(__file__).with_name('check_no_lazy_imports.py'),
        Path(pycodestyle.__file__),
    ]
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def qualify_checkers(entries, candidate, report):
    """Cualifica el candidato exacto; no acepta un recibo declarativo.

    Sólo cubre las superficies aprobadas de admisión. Workflow, protecciones
    y cualquier política ajena siguen rechazadas. El informe conserva comandos,
    JUnit, contenido exacto y resultado de los controles reales.
    """
    touched = {
        path for entry in entries
        for path in [entry['path'], entry['old_path']]
        if path in PROTECTED or path in QUALIFICATION_TESTS
        or path.startswith((
            '.githooks/', '.github/workflows/', '.claude/rules/',
        ))
    }
    if not touched <= QUALIFIED_SURFACES:
        raise Unverifiable('Change is outside qualified checker scope')
    root = Path(git('rev-parse', '--show-toplevel').decode().strip())
    bound = {}
    for path in sorted(QUALIFIED_SURFACES):
        content = git('show', f'{candidate}:{path}')
        if (root / path).read_bytes() != content:
            raise Unverifiable(
                'Working checker differs from candidate: ' + path
            )
        bound[path] = hashlib.sha256(content).hexdigest()
    with tempfile.TemporaryDirectory(prefix='checker-qualification-') as temp:
        junit = Path(temp) / 'qualification.xml'
        command = [
            sys.executable, '-m', 'pytest', '--noconftest', '-c', '/dev/null',
            '-p', 'no:cacheprovider', '-q', *QUALIFICATION_TESTS,
            '--junitxml=' + str(junit),
        ]
        # No ejecuta el ORM ni usa PostgreSQL: sólo los fixtures ya existentes.
        environment = dict(os.environ)
        environment.pop('PYTEST_ADDOPTS', None)
        environment.pop('PYTEST_PLUGINS', None)
        environment.update(
            PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
            PYTHONPATH=str(root / 'scripts'),
        )
        result = subprocess.run(
            command, cwd=root, env=environment, text=True, capture_output=True,
        )
        evidence = {
            'candidate_tree': candidate, 'bound_sha256': bound,
            'command': command, 'exit_code': result.returncode,
            'stdout': result.stdout, 'stderr': result.stderr,
            'junit': junit.read_text() if junit.is_file() else None,
        }
        report['checker_qualification'] = evidence
        if result.returncode or not evidence['junit']:
            raise Unverifiable('Checker qualification did not pass')
        suite = ET.fromstring(evidence['junit'])
        cases = [case.get('name', '') for case in suite.iter('testcase')]
        required = [
            'test_inherited_debt_is_not_global_pass',
            'test_wrong_index_tree_fails_closed',
            'test_new_late_module_import_is_rejected',
            'test_changed_index_during_verification_fails_closed',
            'test_evidence_is_not_reused_when_verifier_changes',
            'test_old_error_can_be_corrected',
            'test_new_file_cannot_inherit_an_old_identical_diagnostic',
            'test_duplicate_diagnostics_do_not_hide_an_added_occurrence',
            'test_real_hook_rejects_invalid_provenance',
            'test_qualification_flag_is_not_a_policy_bypass',
            'test_real_hook_rejects_regressions_and_preserves_other_gates'
            '[clean]',
            'test_real_hook_rejects_regressions_and_preserves_other_gates'
            '[style]',
            'test_real_hook_rejects_regressions_and_preserves_other_gates'
            '[imports]',
            'test_real_hook_rejects_regressions_and_preserves_other_gates'
            '[context]',
        ]
        if any(name not in cases for name in required):
            raise Unverifiable('Required qualification coverage is missing')
        if any(
            list(suite.iter(kind)) for kind in ['failure', 'error', 'skipped']
        ):
            raise Unverifiable(
                'Qualification contains failed or skipped cases'
            )
    for path, digest in bound.items():
        if hashlib.sha256((root / path).read_bytes()).hexdigest() != digest:
            raise Unverifiable('Qualified checker changed during execution')


def evaluate(args, report):
    if pycodestyle.__version__ != '2.14.0':
        raise Unverifiable('Unqualified pycodestyle version')
    base = oid(args.base, 'commit')
    head = git('rev-parse', '--verify', 'HEAD').decode().strip()
    original_verifiers = verifier_hashes()
    report['base'] = base
    if args.index_tree:
        expected = oid(args.index_tree, 'tree')
        if base != head:
            raise Unverifiable(
                'Index admission requires the current HEAD base'
            )
        actual = git('write-tree').decode().strip()
        if actual != expected:
            raise Unverifiable('Index tree differs from declared evidence')
        candidate = expected
        report['candidate'] = {'index_tree': expected, 'head': head}
    else:
        revision = oid(args.candidate, 'commit')
        git('merge-base', '--is-ancestor', base, revision)
        candidate = git('rev-parse', f'{revision}^{{tree}}').decode().strip()
        report['candidate'] = {'revision': revision, 'tree': candidate}
    report['verifiers'] = original_verifiers
    report['python'] = sys.version
    report['pycodestyle'] = pycodestyle.__version__
    report['native_checks'] = {
        'style': 'pycodestyle.Checker.check_all; native defaults, ignore=W503',
        'imports': 'check_no_lazy_imports.find_misplaced_imports',
        'compilation': 'compile(exec), SyntaxWarning treated as error',
    }
    entries = changes(base, candidate)
    protected = any(
        path in PROTECTED or path in QUALIFICATION_TESTS
        or path.startswith((
            '.githooks/', '.github/workflows/', '.claude/rules/',
        ))
        for entry in entries for path in [entry['path'], entry['old_path']]
    )
    if protected:
        if not args.qualify_checkers:
            raise Unverifiable('Policy/verifier change requires qualification')
        qualify_checkers(entries, candidate, report)
    for entry in entries:
        result = evaluate_file(entry)
        if result is not None:
            report['files'].append(result)
    if not entries:
        raise Unverifiable('No changed Python scope was demonstrated')
    report['python_scope'] = 'CHANGED' if report['files'] else 'NONE'
    if args.index_tree and (
        git('write-tree').decode().strip() != candidate
        or git('rev-parse', 'HEAD').decode().strip() != head
    ):
        raise Unverifiable('Index or HEAD changed during qualification')
    if original_verifiers != verifier_hashes():
        raise Unverifiable('Verifier changed during qualification')
    return 1 if any(row['introduced'] for row in report['files']) else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--index-tree')
    selection.add_argument('--candidate')
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--qualify-checkers', action='store_true')
    args = parser.parse_args()
    report = {
        'command': [sys.executable, *sys.argv], 'files': [], 'reasons': [],
        'increment_admission': 'ERROR',
        'global_style_compliance': 'NOT_EVALUATED',
        'ci_verification': 'NOT_EVALUATED',
        'contract_verification': 'NOT_EVALUATED',
        'integration': 'NOT_EVALUATED', 'acceptance': 'NOT_EVALUATED',
        'activation': 'EXPLICIT_INCREMENT_EVALUATION',
    }
    try:
        code = evaluate(args, report)
        report['increment_admission'] = 'FAIL' if code else 'PASS'
    except (
        Unverifiable, OSError, UnicodeError, ValueError, RecursionError,
    ) as error:
        report['reasons'].append(str(error))
        code = 2
    report['exit_code'] = code
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Increment admission: {report["increment_admission"]}; '
          'global style, CI, integration and acceptance are NOT_EVALUATED')
    return code


if __name__ == '__main__':
    sys.exit(main())
