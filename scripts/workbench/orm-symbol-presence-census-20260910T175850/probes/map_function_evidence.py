"""EXPERIMENTAL — medición exploratoria: empareja funciones de módulo con casos
de prueba que las importan desde ese módulo y las llaman. No es autoridad."""
import ast
import pathlib
import sys

rows = pathlib.Path(sys.argv[1]).read_text().splitlines()
pairs = [row.split('\t') for row in rows]
want = {}
for mod, fn in pairs:
    dotted = mod[len('src/'):-3].replace('/', '.')
    want.setdefault(dotted, set()).add(fn)
found = {}
for test in sorted(pathlib.Path('tests').rglob('test_*.py')):
    try:
        tree = ast.parse(test.read_text())
    except SyntaxError:
        continue
    imported = {}
    for n in tree.body:
        if isinstance(n, ast.ImportFrom) and n.module in want:
            for a in n.names:
                if a.name in want[n.module]:
                    imported[a.asname or a.name] = (n.module, a.name)
    if not imported:
        continue

    def visit(node, prefix):
        for n in getattr(node, 'body', []):
            if isinstance(n, ast.ClassDef):
                visit(n, prefix + n.name + '::')
            elif isinstance(n, ast.FunctionDef) and n.name.startswith('test'):
                called = {c.func.id for c in ast.walk(n)
                          if isinstance(c, ast.Call)
                          and isinstance(c.func, ast.Name)}
                for local, (module, fn) in imported.items():
                    key = (module, fn)
                    if local in called and key not in found:
                        found[key] = f'{test}::{prefix}{n.name}'
    visit(tree, '')
for (module, fn), node in sorted(found.items()):
    print(f"src/{module.replace('.', '/')}.py\t{fn}\tfunction\t{node}")
