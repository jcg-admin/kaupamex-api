"""Censo por AST de todo ``@api.constrains`` / ``@constrains`` bajo
``addons/`` y ``src/`` (sin ``migrations``): dónde vive la función
decorada (dentro de una clase o en el módulo) y cómo se llama.

Uso: ``python <este archivo> addons src``. Sólo lee archivos.
"""
import ast
import pathlib
import sys


def is_constrains(node):
    target = node.func if isinstance(node, ast.Call) else node
    if isinstance(target, ast.Attribute):
        return target.attr == 'constrains'
    return isinstance(target, ast.Name) and target.id == 'constrains'


print('path\tline\tscope\tfunction')
for root in sys.argv[1:]:
    for path in sorted(pathlib.Path(root).rglob('*.py')):
        if 'migrations' in path.parts:
            continue
        tree = ast.parse(path.read_text())
        stack = []

        def visit(node, scope):
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.ClassDef):
                    visit(child, child.name)
                elif isinstance(child, (ast.FunctionDef,
                                        ast.AsyncFunctionDef)):
                    if any(is_constrains(d) for d in child.decorator_list):
                        print(f'{path}\t{child.lineno}\t'
                              f'{scope or "<module>"}\t{child.name}')
                    visit(child, scope)
                else:
                    visit(child, scope)

        visit(tree, None)
