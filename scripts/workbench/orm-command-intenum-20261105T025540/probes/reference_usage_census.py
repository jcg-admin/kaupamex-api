"""Cómo consume ``Command`` el árbol de la referencia, por forma de uso.

Recorre por AST todo ``*.py`` bajo la raíz dada (``odoo19c``) y clasifica cada
aparición del nombre ``Command`` (o del atributo ``.Command``):

``factory``      ``Command.create(...)`` y las otras seis llamadas.
``constant``     ``Command.CREATE`` … ``Command.SET`` leído como valor.
``compare``      el valor de una constante dentro de una comparación
                 (``==``, ``!=``, ``in``, ``not in``) o de un ``case``.
``construct``    ``Command(x)``: convierte un entero en miembro.
``member_api``   ``.name`` / ``.value`` sobre un miembro, ``isinstance(x,
                 Command)``, iteración ``for … in Command``.
``other``        cualquier otra aparición (import, alias, contexto de eval).

Escribe el conteo por forma y por archivo, y hasta 5 muestras por forma.
Uso::

    .venv/bin/python <banco>/probes/reference_usage_census.py \
        "$ODOO19C" <salida>
"""
import ast
import collections
import pathlib
import sys

FACTORIES = {'create', 'update', 'delete', 'unlink', 'link', 'clear', 'set'}
CONSTANTS = {'CREATE', 'UPDATE', 'DELETE', 'UNLINK', 'LINK', 'CLEAR', 'SET'}


def is_command(node):
    return ((isinstance(node, ast.Name) and node.id == 'Command')
            or (isinstance(node, ast.Attribute) and node.attr == 'Command'))


ITERATORS = ('tuple', 'list', 'set', 'frozenset', 'iter', 'len', 'sorted')
TYPE_CHECKS = ('isinstance', 'issubclass')


def called_name(node):
    """Nombre de la función si ``node`` es una llamada a un nombre."""
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        return node.func.id
    return None


def classify(tree):
    parents = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    found = []
    for node in ast.walk(tree):
        if not is_command(node):
            continue
        parent = parents.get(node)
        kind = 'other'
        if isinstance(parent, ast.Attribute) and parent.value is node:
            grand = parents.get(parent)
            if parent.attr in FACTORIES and isinstance(grand, ast.Call) \
                    and grand.func is parent:
                kind = 'factory'
            elif parent.attr in CONSTANTS:
                kind = 'constant'
                walker = grand
                while walker is not None and not isinstance(
                        walker, (ast.stmt, ast.Compare, ast.match_case)):
                    walker = parents.get(walker)
                if isinstance(walker, (ast.Compare, ast.match_case)):
                    kind = 'compare'
                elif isinstance(grand, ast.MatchValue):
                    kind = 'compare'
            elif parent.attr in ('name', 'value', '__members__'):
                kind = 'member_api'
        elif isinstance(parent, ast.Call) and parent.func is node:
            kind = 'construct'
        elif called_name(parent) in TYPE_CHECKS:
            kind = 'member_api'
        elif isinstance(parent, (ast.For, ast.comprehension)) \
                and parent.iter is node:
            kind = 'member_api'
        elif called_name(parent) in ITERATORS:
            # ``tuple(Command)``: itera los miembros del enum.
            kind = 'member_api'
        elif isinstance(parent, ast.BinOp) \
                and called_name(parents.get(parent)) in TYPE_CHECKS:
            # ``isinstance(x, Command | int)``.
            kind = 'member_api'
        found.append((kind, node.lineno))
    return found


def main(root, output):
    root = pathlib.Path(root)
    by_kind = collections.Counter()
    by_kind_files = collections.defaultdict(set)
    samples = collections.defaultdict(list)
    files = 0
    for path in sorted(root.rglob('*.py')):
        try:
            source = path.read_text()
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError):
            continue
        files += 1
        lines = source.splitlines()
        for kind, lineno in classify(tree):
            by_kind[kind] += 1
            rel = path.relative_to(root)
            by_kind_files[kind].add(str(rel))
            limit = 40 if kind in ('member_api', 'other') else 5
            if len(samples[kind]) < limit:
                text = lines[lineno - 1].strip()
                samples[kind].append(f'{rel}:{lineno}: {text}')
    with open(output, 'w') as handle:
        handle.write(f'archivos .py recorridos: {files}\n\n')
        handle.write('forma\tapariciones\tarchivos\n')
        for kind in ('factory', 'constant', 'compare', 'construct',
                     'member_api', 'other'):
            handle.write(f'{kind}\t{by_kind[kind]}\t'
                         f'{len(by_kind_files[kind])}\n')
        for kind in ('compare', 'construct', 'member_api', 'constant',
                     'other'):
            handle.write(f'\n# muestras: {kind}\n')
            for line in samples[kind]:
                handle.write(line + '\n')
    print(open(output).read())


if __name__ == '__main__':
    main(*sys.argv[1:3])
