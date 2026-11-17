"""Reproduce ``check_reference_flow`` extendido sobre commits ya hechos.

Sólo lectura: lee cada commit y su padre con ``git show``; el banco de
diseños del padre hace de ``HEAD`` y el del propio commit de índice.
El eje A (``src/orm``) ya existía y no se recuenta.

Uso: ``python replay_reference_flow.py <gate.py> <n_commits> [prefijo]``.
Con ``prefijo`` imprime los hallazgos de ese commit.
"""
import collections
import importlib.util
import subprocess
import sys


def load(path):
    spec = importlib.util.spec_from_file_location('gate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(*args):
    result = subprocess.run(['git', *args], capture_output=True, text=True,
                            check=False)
    return result.stdout if result.returncode == 0 else None


def designs_at(gate, revision):
    paths = (git('ls-tree', '-r', '--name-only', revision,
                 'scripts/workbench') or '').split()
    return {path: git('show', f'{revision}:{path}') or ''
            for path in paths if gate.DESIGNS.match(path)}


def replay(gate, commit):
    files = (git('diff-tree', '--no-commit-id', '-r', '--name-only',
                 '--diff-filter=AM', commit) or '').split()
    targets = [path for path in files
               if gate.in_scope(path) and not path.startswith(gate.ROOT)]
    if not targets:
        return None
    prior = designs_at(gate, f'{commit}^')
    same = designs_at(gate, commit)
    problems = []
    for path in targets:
        new = git('show', f'{commit}:{path}') or ''
        old = git('show', f'{commit}^:{path}')
        problems += gate.flow_problems(path, old, new, prior,
                                       staged_designs=same)
        problems += gate.citation_problems(path, old, new)
    return problems


def main(argv):
    gate = load(argv[1])
    wanted = argv[3] if len(argv) > 3 else None
    totals = collections.Counter()
    for commit in git('rev-list', '--no-merges', f'-{argv[2]}',
                      'HEAD').split():
        problems = replay(gate, commit)
        if problems is None:
            continue
        totals['commits'] += 1
        totals['flagged'] += bool(problems)
        totals['problems'] += len(problems)
        totals['anteriority'] += any('no precede' in p for p in problems)
        if problems and wanted and commit.startswith(wanted):
            for problem in problems:
                print('  ', problem)
    print(dict(totals))


if __name__ == '__main__':
    main(sys.argv)
