#!/usr/bin/env python3
"""
check_no_lazy_imports — gate de zero-tolerance para imports lazy.

Verifica que ningun .py de ``src/**``, ``addons/**`` y ``tests/**``
(excluyendo ``migrations/``) contenga ``Import`` o ``ImportFrom`` dentro
de un ``FunctionDef`` / ``AsyncFunctionDef``.

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
import re
import sys
from pathlib import Path

# Raíces que recorre sin argumentos, resueltas desde ``__file__`` y NO desde el
# CWD. Eran relativas: corrido desde cualquier otro directorio, el ``rglob``
# devolvía 0 archivos y el script salía 0 **sin imprimir nada** — un
# cero que se
# lee como limpieza. Ver H-API-336; mismo defecto que H-API-335 en
# ``check_silent_oks.py``, del que se copia el manejo.
# ``src`` ENTERO, no ``src/addons``: la regla dice "TODO .py en api/", y el
# recorte anterior dejaba fuera ``src/orm``, ``src/tools``, ``src/modules`` y
# los módulos sueltos de la raíz. Cuatro imports dentro de función en
# ``src/tools/convert.py`` pasaron sin que el gate los viera (tarea #115): su
# verde no distinguía "no hay lazy" de "no miro ahí" — sub-patrón D de
# ``metrica-decide-la-conclusion.md``.
DEFAULT_ROOTS = ('src', 'addons', 'tests')


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


def find_misplaced_imports(tree: ast.Module):
    """Detecta imports anidados o posteriores al bloque inicial del
    módulo."""
    initial = set()
    for index, node in enumerate(tree.body):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            initial.add(id(node))
        elif isinstance(node, ast.Try) and all(
            isinstance(item, (ast.Import, ast.ImportFrom))
            for item in node.body
        ) and all(
            isinstance(handler.type, ast.Name)
            and handler.type.id in {'ImportError', 'ModuleNotFoundError'}
            for handler in node.handlers
        ):
            # Dependencias opcionales, sólo en el bloque inicial.
            initial.update(id(item) for item in node.body)
            for handler in node.handlers:
                for item in handler.body:
                    if not isinstance(item, (ast.Import, ast.ImportFrom)):
                        break
                    initial.add(id(item))
        elif isinstance(node, ast.If) and (
            ast.unparse(node.test) in {
                'TYPE_CHECKING', 'typing.TYPE_CHECKING',
                "os.name == 'nt'", "sys.platform == 'win32'",
            }
        ):
            for item in node.body:
                if not isinstance(item, (ast.Import, ast.ImportFrom)):
                    break
                initial.add(id(item))
        elif (
            index == 0
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue
        elif isinstance(node, ast.Assign) and all(
            isinstance(target, ast.Name)
            and target.id.startswith('__')
            and target.id.endswith('__')
            for target in node.targets
        ):
            try:
                ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError):
                break
            continue
        else:
            break
    for node in ast.walk(tree):
        if (
            isinstance(node, (ast.Import, ast.ImportFrom))
            and id(node) not in initial
        ):
            yield node.lineno, ast.unparse(node)


def collect_files(args: list[str]) -> list[Path]:
    if args:
        # Modo pre-commit: rutas explicitas.
        sources = []
        for argument in args:
            path = Path(argument)
            if path.suffix == '.py':
                sources.append(path)
            elif path.is_file():
                with path.open('rb') as source:
                    first_line = source.readline()
                if re.match(
                    rb'^#!.*[/\s]python(?:\d+(?:\.\d+)*)?(?:\s|$)',
                    first_line,
                ):
                    sources.append(path)
        return sources
    # Modo audit completo — resuelto desde el script, no desde el CWD.
    base = Path(__file__).resolve().parent.parent
    out = []
    for nombre in DEFAULT_ROOTS:
        root = base / nombre
        if not root.is_dir():
            print(f'check_no_lazy_imports: raíz ausente, se omite: {nombre}')
            continue
        out.extend(root.rglob('*.py'))
    return out


def main(argv: list[str]) -> int:
    strict = '--top-level' in argv
    argv = [arg for arg in argv if arg != '--top-level']
    files = collect_files(argv)
    if not files:
        if argv:
            # Modo pre-commit sin .py staged: no hay nada que validar y eso
            # es legítimo — el conjunto vacío lo fijó el commit, no el gate.
            return 0
        # Modo audit: un conjunto vacío significa que el gate no encontró su
        # árbol. No puede afirmar nada, así que no dice OK.
        print(
            'check_no_lazy_imports: 0 archivos que medir — el gate no puede '
            'afirmar nada. Revisa DEFAULT_ROOTS.'
        )
        return 2

    parse_errors = 0
    medidos = 0
    findings: list[tuple[Path, int, str]] = []

    for path in files:
        if '__pycache__' in path.parts or (
            'migrations' in path.parts and not strict
        ):
            continue
        medidos += 1
        try:
            src = path.read_text()
        except OSError as e:
            print(f'  WARN: cannot read {path}: {e}', file=sys.stderr)
            parse_errors += 1
            continue
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError as e:
            print(f'  PARSE_ERROR {path}:{e.lineno}: {e.msg}', file=sys.stderr)
            parse_errors += 1
            continue
        finder = find_misplaced_imports if strict else find_lazy_imports
        for lineno, stmt in finder(tree):
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
            'Lazy imports estan PROHIBIDOS en src/**, addons/** y tests/**.',
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

    # El denominador va junto al veredicto: un "OK" sin él no distingue un
    # árbol limpio de un instrumento ciego (H-API-335).
    print(f'OK: sin lazy imports ({medidos} archivos medidos).')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
