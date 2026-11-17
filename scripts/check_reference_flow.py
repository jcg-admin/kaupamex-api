#!/usr/bin/env python3
"""Gate: un cambio de comportamiento ORM se apoya en el flujo medido de la
referencia, estudiado ANTES de cambiar el código.

Instrucción 4.3.2 §6 y la lección del 2026-09-03 (``transaction_scope``,
``convert_to_column`` diferido, la nulabilidad de ``Integer`` afirmada sin
medir): los tres defectos pasaron todos los gates porque ninguno miraba si
lo que el código dice de la fuente es cierto, ni si hubo un estudio del
flujo antes de cambiar el mecanismo. Éste actúa ANTES de integrar.
Instrucción 4.3.3 §8 lo extiende a los addons y a la anterioridad del
estudio (``scripts/workbench/orm-continuation-plan-20261103T095630/designs/
reference-flow-gate-addons.md``).

Tres ejes, sobre el incremento (``HEAD`` contra el índice):

**Citas.** Cada cita NUEVA de la forma ``≙ ``Clase.nombre`` (``:N``)``
tiene que resolver por AST en la referencia: la línea ``N`` cae dentro de
la definición de ``nombre`` (``def``, ``class`` o asignación, con dos
líneas de holgura para el decorador), primero en el archivo espejo y si no
en un único archivo del mismo paquete. Espejos: ``src/orm/x.py`` ↔
``odoo/orm/x.py``, ``src/addons/base/models/x.py`` ↔
``odoo/addons/base/models/x.py`` y ``addons/a/models/x.py`` ↔
``addons/a/models/x.py``. Una cita ``odoo19c: <ruta>:<N>[-<M>]`` exige que
la ruta exista y que el rango quepa en el archivo. Las citas que ya
estaban en ``HEAD`` no se juzgan: la deuda heredada se paga al tocarla.

**Flujo.** Cinco clases de cambio (§8.3):

- A, cuerpo de función cambiado en ``src/orm``; B, cuerpo de método
  cambiado en un modelo de addon con espejo en la referencia; C,
  declaración de campo cambiada en un modelo de addon o migración nueva.
  Las tres exigen un diseño del banco (``scripts/workbench/*/designs/
  *.md``) que nombre el símbolo (o la migración), lleve una cita que
  resuelva y nombre una prueba existente bajo ``tests/``.
- D, sólo docstring, comentario o formato: el volcado AST no cambia y no
  exige nada.
- E, cuerpo cambiado en un modelo de addon SIN espejo en la referencia:
  exige el diseño y la prueba, no una cita (no se inventa una contraparte).

**Anterioridad.** El diseño cuenta sólo en su versión de ``HEAD``: el
estudio se commitea antes que el código que sustenta. Uno que sólo está en
el índice del mismo commit produce su propio hallazgo. La prueba se busca
en el árbol de trabajo: nace con la implementación.

Salida: ``0`` sin hallazgos, ``1`` con un renglón por hallazgo, ``2`` si no
pudo medir (falta la referencia): un cero sin referencia sería un verde
falso.

Métrica: citas nuevas y símbolos cambiados en ``src/orm``, en
``models/`` y ``migrations/`` de los addons.
Ciega a: si la conducta del código coincide con la de la referencia —eso
lo deciden las pruebas discriminantes—; a dependencias no reconciliadas y
divergencias sin decisión, que no tienen forma léxica; a citas en prosa
libre sin una de las dos formas; y a controladores, asistentes y
``src/tools``.
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
#: Modelos de addon: ``addons/a/models/x.py`` y ``src/addons/a/models/x.py``.
MODEL_FILE = re.compile(r'^(src/)?addons/([^/]+)/models/[^/]+\.py$')
MIGRATION_FILE = re.compile(r'^(src/)?addons/[^/]+/migrations/[^/]+\.py$')
#: Módulos cuyos llamados declaran un campo en el cuerpo de una clase.
FIELD_MODULES = {'fields', 'models', 'dj_models'}

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


@functools.lru_cache(maxsize=None)
def defines_at(path, name, line):
    """¿La línea ``line`` de ``path`` cae en la definición de ``name``?"""
    return any(start - SLACK <= line <= end
               for start, end in definitions(path).get(name, ()))


def mirror_for(our_path, reference=REFERENCE):
    """``(archivo espejo, paquete)`` de la referencia para ``our_path``."""
    pure = pathlib.PurePath(our_path)
    if our_path.startswith(ROOT):
        package = reference / 'odoo' / 'orm'
    elif (match := MODEL_FILE.match(our_path)):
        addon = match.group(2)
        package = (reference / 'odoo' / 'addons' / addon / 'models'
                   if match.group(1) else
                   reference / 'addons' / addon / 'models')
    else:
        package = reference / 'odoo' / 'orm'
    return package / pure.name, package


def resolve_symbol(our_path, name, line, reference=REFERENCE):
    """¿La cita ``≙ ``…name`` (``:line``)`` resuelve en la referencia?"""
    mirror, package = mirror_for(our_path, reference)
    if mirror.exists() and defines_at(mirror, name, line):
        return True
    if not package.is_dir():
        return False
    hits = [path for path in sorted(package.glob('*.py'))
            if path != mirror and defines_at(path, name, line)]
    return len(hits) == 1


def resolve_path(relpath, first, last, reference=REFERENCE, our_path=None):
    """¿La cita ``odoo19c: relpath:first[-last]`` cabe en el archivo?

    Una ruta sin directorio (``odoo19c: purchase_order.py:N``) es la forma
    corta que usan los modelos de addon: se busca en el paquete espejo de
    ``our_path``.
    """
    path = reference / relpath
    if not path.is_file() and our_path and '/' not in relpath:
        path = mirror_for(our_path, reference)[1] / relpath
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
    return resolve_path(citation[1], citation[2], citation[3], reference,
                        our_path)


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


def _declares_field(node):
    """¿La asignación de clase ``node`` declara un campo?"""
    value = node.value
    return (isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id in FIELD_MODULES)


def _bodies(text, with_fields=False):
    """``{nombre calificado: volcado del cuerpo sin docstring}``.

    Con ``with_fields``, también las declaraciones de campo de cada clase
    (``Clase.campo``): un cambio de su política es comportamiento.
    """
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
            elif (with_fields and prefix and isinstance(child, ast.Assign)
                  and _declares_field(child)):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        bodies[f'{prefix}{target.id}'] = ast.dump(
                            child.value)

    visit(ast.parse(text), '')
    return bodies


def changed_functions(old_text, new_text, with_fields=False):
    """Símbolos nuevos o con cuerpo distinto; un docstring no cuenta."""
    old = _bodies(old_text, with_fields) if old_text else {}
    return sorted(name for name, dump in
                  _bodies(new_text, with_fields).items()
                  if old.get(name) != dump)


def design_covers(name, designs, our_path, reference=REFERENCE,
                  tests_root=pathlib.Path('tests'), need_citation=True):
    """¿Un diseño nombra el símbolo, cita la fuente y nombra la prueba?"""
    short = name.rsplit('.', 1)[-1]
    word = re.compile(rf'\b{re.escape(short)}\b')
    for text in designs.values():
        if not word.search(text):
            continue
        cited = (not need_citation
                 or any(resolves(our_path, c, reference)
                        for c in citations(text)))
        tested = any((tests_root.parent / t).is_file()
                     for t in TEST_PATH.findall(text))
        if cited and tested:
            return True
    return False


def change_kind(path, reference=REFERENCE):
    """La clase del cambio de ``path``: ``A``, ``B``, ``C``, ``E`` o ``None``.

    ``B`` y ``E`` se separan por la existencia del archivo espejo; la
    migración es ``C``. ``D`` no es una clase de archivo sino de cambio:
    la da :func:`changed_functions` vacío.
    """
    if path.startswith(ROOT) and path.endswith('.py'):
        return 'A'
    if MODEL_FILE.match(path):
        mirror, _package = mirror_for(path, reference)
        return 'B' if mirror.exists() else 'E'
    if MIGRATION_FILE.match(path):
        return 'C'
    return None


def flow_problems(path, old_text, new_text, designs, reference=REFERENCE,
                  tests_root=pathlib.Path('tests'), staged_designs=None):
    """Los símbolos cambiados sin un diseño previo que los cubra.

    ``designs`` es el banco de ``HEAD``; ``staged_designs`` el del índice.
    Un símbolo que sólo cubre un diseño del índice tiene su propio
    hallazgo: el estudio no precede al cambio.
    """
    kind = change_kind(path, reference)
    if kind is None:
        return []
    if kind == 'C' and MIGRATION_FILE.match(path):
        names = [] if old_text else [pathlib.PurePath(path).stem]
    else:
        names = changed_functions(old_text, new_text,
                                  with_fields=kind in ('B', 'E'))
    need_citation = kind != 'E'
    problems = []
    for name in names:
        if design_covers(name, designs, path, reference, tests_root,
                         need_citation):
            continue
        if staged_designs and design_covers(name, staged_designs, path,
                                            reference, tests_root,
                                            need_citation):
            problems.append(f'{path}: el diseño que cubre {name} no '
                            'precede al cambio (sólo está en el índice, no '
                            'en HEAD)')
        else:
            problems.append(f'{path}: {name} cambia de comportamiento sin un '
                            'diseño que la nombre, cite la referencia y '
                            'nombre su prueba')
    return problems


def _git(*args):
    result = subprocess.run(['git', *args], capture_output=True, text=True,
                            check=False)
    return result.stdout if result.returncode == 0 else None


def in_scope(path):
    """¿El gate mide ``path``? (``.py`` de ``src/orm``, modelos o
    migraciones de addon)."""
    return (path.endswith('.py')
            and (path.startswith(ROOT) or bool(MODEL_FILE.match(path))
                 or bool(MIGRATION_FILE.match(path))))


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
    design_paths = [path for path in (_git('ls-files', 'scripts/workbench')
                                      or '').split() if DESIGNS.match(path)]
    designs = {path: _git('show', f'HEAD:{path}') or ''
               for path in design_paths}
    staged_designs = {path: _git('show', f':{path}') or ''
                      for path in design_paths}
    targets = [path for path in staged if in_scope(path)]
    problems = []
    for path in targets:
        new_text = _git('show', f':{path}') or ''
        old_text = _git('show', f'HEAD:{path}')
        problems += citation_problems(path, old_text, new_text,
                                      args.reference)
        problems += flow_problems(path, old_text, new_text, designs,
                                  args.reference,
                                  staged_designs=staged_designs)
    for problem in problems:
        print(problem)
    kinds = collections.Counter(change_kind(path, args.reference)
                                for path in targets)
    verdict = 'FALLA' if problems else 'OK'
    scope = ', '.join(f'{kind} {kinds[kind]}' for kind in sorted(kinds))
    print(f'check_reference_flow: {verdict} — {len(problems)} hallazgo(s) '
          f'(alcance medido: {len(targets)} archivo(s): {scope or "ninguno"})')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
