"""Usos de ``env[...]`` que exigen la CLASE del modelo y no un recordset.

Cuenta los usos directos de ``env[...]`` y sigue ``X = env[...]`` dentro de
su función. Uso: ``python env_flow_census.py <raíz> [<raíz> ...]``.

Ciego al flujo entre funciones y a una variable reasignada con otro origen
en la misma función (se cuenta igual).
"""
import ast
import collections
import pathlib
import sys

CLASS_ONLY_ATTRS = {
    'objects', 'DoesNotExist', 'MultipleObjectsReturned', '__name__',
    '__qualname__', '__mro__', '_default_manager', '_base_manager',
    '__subclasses__', 'mro',
}
CLASS_BUILTINS = ('issubclass', 'isinstance', 'super', 'type')

hits = collections.Counter()
examples = collections.defaultdict(list)


def is_env_subscript(node):
    """Si el nodo es ``<algo>.env[...]`` o ``env[...]``."""
    if not isinstance(node, ast.Subscript):
        return False
    value = node.value
    if isinstance(value, ast.Attribute):
        return value.attr == 'env'
    return getattr(value, 'id', None) == 'env'


def note(kind, path, line):
    hits[kind] += 1
    if len(examples[kind]) < 6:
        examples[kind].append(f'{path}:{line}')


def classify(node, parent):
    """El uso que exige la clase, o ``None``."""
    if isinstance(parent, ast.Attribute) and parent.attr in CLASS_ONLY_ATTRS:
        return parent.attr
    if isinstance(parent, ast.Call) and parent.func is node:
        return 'call'
    if isinstance(parent, ast.Compare) and any(
            isinstance(op, (ast.Is, ast.IsNot)) for op in parent.ops):
        return 'is'
    if (isinstance(parent, ast.Call)
            and getattr(parent.func, 'id', None) in CLASS_BUILTINS):
        return parent.func.id
    if isinstance(parent, ast.Dict) and node in parent.keys:
        return 'dictkey'
    return None


def scan(path):
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    for node in ast.walk(tree):
        if is_env_subscript(node):
            kind = classify(node, parents.get(node))
            if kind:
                note('direct.' + kind, path, node.lineno)
    scopes = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)
    for scope in ast.walk(tree):
        if not isinstance(scope, scopes):
            continue
        names = {
            target.id
            for node in ast.walk(scope)
            if isinstance(node, ast.Assign) and is_env_subscript(node.value)
            for target in node.targets if isinstance(target, ast.Name)
        }
        for node in ast.walk(scope):
            if (isinstance(node, ast.Name) and node.id in names
                    and isinstance(node.ctx, ast.Load)):
                kind = classify(node, parents.get(node))
                if kind:
                    note('var.' + kind, path, node.lineno)


def main(roots):
    for root in roots:
        for path in pathlib.Path(root).rglob('*.py'):
            if 'migrations' not in path.parts and '.venv' not in path.parts:
                scan(path)
    for kind, count in hits.most_common():
        print(count, kind, examples[kind])


if __name__ == '__main__':
    main(sys.argv[1:])
