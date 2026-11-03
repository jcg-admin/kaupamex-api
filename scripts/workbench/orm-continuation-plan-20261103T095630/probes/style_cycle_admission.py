#!/usr/bin/env python3
"""Verifica la admisión de estilo del ciclo: base ``9d18694d`` contra ``HEAD``.

No es un checker nuevo: llama a ``evaluate_file`` de
``scripts/check_python_style_increment.py`` sobre las rutas que lista
``outputs/style-admission-cycle-9d18694d.txt`` y sale 1 si alguna no es
``PASS`` (``FAIL`` o ``UNVERIFIABLE``). Es el ``verify`` del ítem
``style-admission-debt``.
"""
import importlib.util
import pathlib
import subprocess
import sys

BENCH = pathlib.Path(__file__).resolve().parents[1]
REPO = BENCH.parents[2]
BASE = '9d18694d'

sys.path.insert(0, str(REPO / 'scripts'))
spec = importlib.util.spec_from_file_location(
    'increment', REPO / 'scripts' / 'check_python_style_increment.py')
increment = importlib.util.module_from_spec(spec)
spec.loader.exec_module(increment)


def main():
    listing = BENCH / 'outputs' / 'style-admission-cycle-9d18694d.txt'
    paths = {line.split()[1] for line in listing.read_text().splitlines()
             if line.strip()}
    base = subprocess.run(['git', '-C', str(REPO), 'rev-parse', BASE],
                          check=True, capture_output=True,
                          text=True).stdout.strip()
    tree = subprocess.run(['git', '-C', str(REPO), 'rev-parse', 'HEAD^{tree}'],
                          check=True, capture_output=True,
                          text=True).stdout.strip()
    seen, failing = set(), []
    for change in increment.changes(base, tree):
        if change['path'] not in paths:
            continue
        seen.add(change['path'])
        try:
            decision = increment.evaluate_file(change)['decision']
        except increment.Unverifiable as error:
            decision = f'UNVERIFIABLE ({error})'
        if decision != 'PASS':
            failing.append(f'{decision} {change["path"]}')
    missing = sorted(paths - seen)
    for line in failing:
        print(line)
    print(f'style cycle: {len(seen) - len(failing)} PASS de {len(seen)} '
          f'medidas; {len(missing)} sin cambio frente a la base')
    return 1 if failing else 0


if __name__ == '__main__':
    sys.exit(main())
