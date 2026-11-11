"""Nombres leídos en funciones que no define ni el módulo, ni la función,
ni builtins. Control estático barato antes de un ci-multidb de 35 min."""
import ast
import builtins
import sys


def undefined(path):
    tree = ast.parse(open(path).read())
    module = set(dir(builtins))
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                          ast.ClassDef)):
            module.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            module |= {(a.asname or a.name).split('.')[0] for a in n.names}
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            targets = n.targets if isinstance(n, ast.Assign) else [n.target]
            for t in targets:
                module |= {x.id for x in ast.walk(t)
                           if isinstance(x, ast.Name)}
    missing = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local = {a.arg for a in fn.args.args + fn.args.kwonlyargs}
        local |= {x.id for x in ast.walk(fn)
                  if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store)}
        for x in ast.walk(fn):
            if (isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)
                    and x.id not in module and x.id not in local):
                missing.add((x.id, x.lineno))
    return sorted(missing)


if __name__ == '__main__':
    for path in sys.argv[1:]:
        print(path, undefined(path) or 'sin nombres sin definir')
