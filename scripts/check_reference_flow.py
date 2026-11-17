#!/usr/bin/env python3
"""Gate: un cambio de comportamiento en ``src/orm`` se apoya en el flujo
medido de la referencia.

Instrucción 4.3.2 §6 y la lección del 2026-09-03 (``transaction_scope``,
``convert_to_column`` diferido, la nulabilidad de ``Integer`` afirmada sin
medir): los tres defectos pasaron todos los gates porque ninguno miraba si
lo que el código dice de la fuente es cierto, ni si hubo un estudio del
flujo antes de cambiar el mecanismo. Éste actúa ANTES de integrar.

Dos ejes, sobre el incremento (``HEAD`` contra el índice):

**Citas.** Cada cita NUEVA de la forma ``≙ ``Clase.nombre`` (``:N``)``
tiene que resolver por AST en la referencia: la línea ``N`` cae dentro de
la definición de ``nombre`` (``def``, ``class`` o asignación, con dos
líneas de holgura para el decorador), primero en el archivo espejo
(``src/orm/x.py`` ↔ ``odoo/orm/x.py``) y si no en un único archivo del
mismo paquete. Una cita ``odoo19c: <ruta>:<N>[-<M>]`` exige que la ruta
exista y que el rango quepa en el archivo. Las citas que ya estaban en
``HEAD`` no se juzgan: la deuda heredada se paga al tocarla.

**Flujo.** Una función o método de ``src/orm`` cuyo cuerpo cambia (no
sólo su docstring) exige un diseño del banco
(``scripts/workbench/*/designs/*.md``, en el índice) que nombre la
función, lleve al menos una cita de la referencia que resuelva y nombre
una prueba existente bajo ``tests/``. Un cambio sólo de docstring o
comentario no lo exige.

Salida: ``0`` sin hallazgos, ``1`` con un renglón por hallazgo, ``2`` si no
pudo medir (falta la referencia): un cero sin referencia sería un verde
falso.

Métrica: citas nuevas y funciones con cuerpo cambiado en ``src/orm``.
Ciega a: si la conducta del código coincide con la de la referencia —eso
lo deciden las pruebas discriminantes—; a citas en prosa libre sin una de
las dos formas; y a otras raíces espejadas (``src/tools``, addons), que
se suman cuando su forma de cita esté medida.
"""
import argparse
import ast
import collections
import functools
import pathlib
import re
import subprocess
import sys

REFERENCE = pathlib.Path(
    '/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0')
ROOT = 'src/orm/'
DESIGNS = re.compile(r'^scripts/workbench/[^/]+/designs/[^/]+\.md$')

#: ``≙ ``Clase.nombre`` (``:N`` — el nombre es el último componente.
SYMBOL_CITATION = re.compile(
    r'≙ ``(?:[A-Za-z_]\w*\.)*([A-Za-z_]\w*)(?:\(\))?`` \(``:(\d+)')
#: ``odoo19c: ruta/archivo.py:N`` o ``:N-M``.
PATH_CITATION = re.compile(
    r'odoo19c: ([A-Za-z0-9_./-]+\.py):(\d+)(?:-(\d+))?')
TEST_PATH = re.compile(r'\btests/[\w/]+\.py\b')
#: Holgura antes del ``def``: el decorador o la línea en blanco previa.
SLACK = 2


@functools.lru_cache(maxsize=None)
def definitions(path):
    """``{nombre: [(inicio, fin), ...]}`` de defs, clases y asignaciones."""
    spans = collections.defaultdict(list)
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            spans[node.name].append((node.lineno, node.end_lineno))
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        else:
            targets = []
        for target in targets:
            if isinstance(target, ast.Name):
                spans[target.id].append((node.lineno, node.end_lineno))
            elif isinstance(target, ast.Attribute):
                spans[target.attr].append((node.lineno, node.end_lineno))
    return spans


def defines_at(path, name, line):
    """¿La línea ``line`` de ``path`` cae en la definición de ``name``?"""
    return any(start - SLACK <= line <= end
               for start, end in definitions(path).get(name, ()))


def resolve_symbol(our_path, name, line, reference=REFERENCE):
    """¿La cita ``≙ ``…name`` (``:line``)`` resuelve en la referencia?"""
    package = reference / 'odoo' / 'orm'
    mirror = package / pathlib.PurePath(our_path).name
    if mirror.exists() and defines_at(mirror, name, line):
        return True
    hits = [path for path in sorted(package.glob('*.py'))
            if path != mirror and defines_at(path, name, line)]
    return len(hits) == 1


def resolve_path(relpath, first, last, reference=REFERENCE):
    """¿La cita ``odoo19c: relpath:first[-last]`` cabe en el archivo?"""
    path = reference / relpath
    if not path.is_file():
        return False
    size = len(path.read_text(encoding='utf-8').splitlines())
    return 1 <= first <= (last or first) <= size


def citations(text):
    """Las citas de ``text`` como tuplas comparables."""
    found = {('symbol', m.group(1), int(m.group(2)))
             for m in SYMBOL_CITATION.finditer(text)}
    found |= {('path', m.group(1), int(m.group(2)),
               int(m.group(3)) if m.group(3) else None)
              for m in PATH_CITATION.finditer(text)}
    return found


def resolves(our_path, citation, reference=REFERENCE):
    if citation[0] == 'symbol':
        return resolve_symbol(our_path, citation[1], citation[2], reference)
    return resolve_path(citation[1], citation[2], citation[3], reference)


def citation_problems(path, old_text, new_text, reference=REFERENCE):
    """Las citas nuevas de ``path`` que no resuelven."""
    new = citations(new_text) - citations(old_text or '')
    return [f'{path}: la cita {_render(c)} no resuelve en la referencia'
            for c in sorted(new, key=str)
            if not resolves(path, c, reference)]


def _render(citation):
    if citation[0] == 'symbol':
        return f'``{citation[1]}`` (``:{citation[2]}``)'
    tail = f'-{citation[3]}' if citation[3] else ''
    return f'odoo19c: {citation[1]}:{citation[2]}{tail}'


def _bodies(text):
    """``{nombre calificado: volcado del cuerpo sin docstring}``."""
    bodies = {}

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                name = f'{prefix}{child.name}'
                if not isinstance(child, ast.ClassDef):
                    body = list(child.body)
                    if (body and isinstance(body[0], ast.Expr)
                            and isinstance(body[0].value, ast.Constant)
                            and isinstance(body[0].value.value, str)):
                        body = body[1:]
                    bodies[name] = ast.dump(ast.Module(body=body,
                                                       type_ignores=[]))
                visit(child, f'{name}.')

    visit(ast.parse(text), '')
    return bodies


def changed_functions(old_text, new_text):
    """Funciones nuevas o con cuerpo distinto; un docstring no cuenta."""
    old = _bodies(old_text) if old_text else {}
    return sorted(name for name, dump in _bodies(new_text).items()
                  if old.get(name) != dump)


def design_covers(name, designs, our_path, reference=REFERENCE,
                  tests_root=pathlib.Path('tests')):
    """¿Algún diseño nombra la función, cita la fuente y nombra su prueba?"""
    short = name.rsplit('.', 1)[-1]
    word = re.compile(rf'\b{re.escape(short)}\b')
    for text in designs.values():
        if not word.search(text):
            continue
        cited = any(resolves(our_path, c, reference)
                    for c in citations(text))
        tested = any((tests_root.parent / t).is_file()
                     for t in TEST_PATH.findall(text))
        if cited and tested:
            return True
    return False


def flow_problems(path, old_text, new_text, designs, reference=REFERENCE,
                  tests_root=pathlib.Path('tests')):
    """Las funciones con cuerpo cambiado sin diseño de flujo que las cubra."""
    return [f'{path}: {name} cambia de comportamiento sin un diseño que la '
            'nombre, cite la referencia y nombre su prueba'
            for name in changed_functions(old_text, new_text)
            if not design_covers(name, designs, path, reference, tests_root)]


def _git(*args):
    result = subprocess.run(['git', *args], capture_output=True, text=True,
                            check=False)
    return result.stdout if result.returncode == 0 else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--reference', type=pathlib.Path, default=REFERENCE)
    args = parser.parse_args(argv)
    if not (args.reference / 'odoo' / 'orm').is_dir():
        print(f'ERROR: falta la referencia en {args.reference}; '
              'no se emite conteo', file=sys.stderr)
        return 2
    staged = (_git('diff', '--cached', '--name-only', '--diff-filter=AM')
              or '').split()
    designs = {path: _git('show', f':{path}') or ''
               for path in (_git('ls-files', 'scripts/workbench') or ''
                            ).split() if DESIGNS.match(path)}
    targets = [path for path in staged
               if path.startswith(ROOT) and path.endswith('.py')]
    problems = []
    for path in targets:
        new_text = _git('show', f':{path}') or ''
        old_text = _git('show', f'HEAD:{path}')
        problems += citation_problems(path, old_text, new_text,
                                      args.reference)
        problems += flow_problems(path, old_text, new_text, designs,
                                  args.reference)
    for problem in problems:
        print(problem)
    verdict = 'FALLA' if problems else 'OK'
    print(f'check_reference_flow: {verdict} — {len(problems)} hallazgo(s) '
          f'(alcance medido: {len(targets)} archivo(s) de {ROOT})')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
