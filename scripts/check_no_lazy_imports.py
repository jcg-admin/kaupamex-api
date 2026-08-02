#!/usr/bin/env python3
"""
check_no_lazy_imports — gate de zero-tolerance para imports lazy.

Verifica que ningun .py de ``src/addons/**`` (excluyendo
``migrations/``) contenga ``Import`` o ``ImportFrom`` dentro de un
``FunctionDef`` / ``AsyncFunctionDef``.

Uso:

    # Validar el repo entero (CI):
    python3 scripts/check_no_lazy_imports.py

    # Validar archivos especificos (pre-commit hook con staged files):
    python3 scripts/check_no_lazy_imports.py path/to/a.py path/to/b.py

Exit codes:
    0  -- todo limpio.
    1  -- hay 1+ lazy imports detectados.
    2  -- error de parseo (algun archivo no es Python valido).

Origen: iniciativa eliminar-lazy-imports-pep8 en docs.
Referencia: PEP 8 imports section + DEC-LAZY-1..6.

NO requiere dependencias externas — solo stdlib.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

DEFAULT_ROOTS = [
    Path('src/addons'),
    Path('tests'),
]


def find_lazy_imports(tree: ast.AST):
    """Yield (lineno, statement_str) por cada import dentro de funcion."""
    for parent in ast.walk(tree):
        if not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(parent):
            if node is parent:
                continue
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                try:
                    stmt = ast.unparse(node)
                except Exception:
                    stmt = '<unparseable>'
                yield node.lineno, stmt


def collect_files(args: list[str]) -> list[Path]:
    if args:
        # Modo pre-commit: rutas explicitas.
        return [Path(a) for a in args if a.endswith('.py')]
    # Modo audit completo — itera por todos los roots default.
    out = []
    for root in DEFAULT_ROOTS:
        if root.exists():
            out.extend(root.rglob('*.py'))
            continue
        # Permite correr desde la raiz del monorepo (con 'api/' prefix).
        alt = Path('api') / root
        if alt.exists():
            out.extend(alt.rglob('*.py'))
    return out


def main(argv: list[str]) -> int:
    files = collect_files(argv)
    if not files:
        # Nada que validar — caso pre-commit sin .py staged.
        return 0

    parse_errors = 0
    findings: list[tuple[Path, int, str]] = []

    for path in files:
        if 'migrations' in path.parts or '__pycache__' in path.parts:
            continue
        try:
            src = path.read_text()
        except OSError as e:
            print(f'  WARN: cannot read {path}: {e}', file=sys.stderr)
            continue
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError as e:
            print(f'  PARSE_ERROR {path}:{e.lineno}: {e.msg}', file=sys.stderr)
            parse_errors += 1
            continue
        for lineno, stmt in find_lazy_imports(tree):
            findings.append((path, lineno, stmt))

    if findings:
        print('LAZY IMPORTS DETECTED:', file=sys.stderr)
        print('', file=sys.stderr)
        for path, lineno, stmt in findings:
            print(f'  {path}:{lineno}: {stmt}', file=sys.stderr)
        print('', file=sys.stderr)
        print(
            f'  Total: {len(findings)} lazy import(s).',
            file=sys.stderr,
        )
        print('', file=sys.stderr)
        print(
            'Lazy imports estan PROHIBIDOS en src/addons/** y tests/**.',
            file=sys.stderr,
        )
        print(
            'Movelos al top-level del modulo. Ver iniciativa',
            file=sys.stderr,
        )
        print(
            '  docs/source/gestion/pm/api/iniciativas/'
            'eliminar-lazy-imports-pep8/',
            file=sys.stderr,
        )
        print(
            'para el razonamiento y las excepciones documentadas (none).',
            file=sys.stderr,
        )
        return 1

    if parse_errors:
        print(
            f'  {parse_errors} archivo(s) con error de parseo.',
            file=sys.stderr,
        )
        return 2

    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
