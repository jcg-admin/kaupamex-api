#!/usr/bin/env python3
"""Asienta un ítem del plan ejecutado por la sesión conversacional.

Es la vía ``preexisting`` de ``thyrox: src/session/task_continuation.py``
(``run_one``): si el ``verify`` del ítem pasa, se escriben ``attempt`` y
``accepted`` en ``outputs/continuation.jsonl`` con ``append_log`` del propio
controlador; si no pasa, ``attempt`` con su salida y ningún ``accepted``. No
decide qué ítem sigue: eso es ``task_continuation next``.

El commit que se cita es el del consumidor en el momento del ``verify``; un
árbol sucio rehúsa con exit 2, porque el veredicto no correspondería a ningún
commit.

Precondición declarada: el entorno trae las variables de base de datos y
``SECRET_KEY`` que la suite necesita (no se guardan en Git).

Uso::

    THYROX_ROOT=/home/user/thyrox python3 probes/settle_item.py <banco> <ítem>
"""
import json
import os
import pathlib
import subprocess
import sys

THYROX = pathlib.Path(os.environ.get('THYROX_ROOT', '/home/user/thyrox'))
sys.path.insert(0, str(THYROX / 'src'))
from session.task_continuation import append_log  # noqa: E402

REPO = pathlib.Path(__file__).resolve().parents[4]


def plan_row(workbench, item):
    for line in (workbench / 'plan.jsonl').read_text().splitlines():
        row = json.loads(line)
        if row['id'] == item:
            return row
    raise SystemExit(f'settle_item: el plan no declara {item!r}')


def main(argv):
    workbench, item = pathlib.Path(argv[0]).resolve(), argv[1]
    row = plan_row(workbench, item)
    # El registro del propio banco cambia con cada asiento: no ensucia el
    # veredicto, que es del codigo.
    own_log = str((workbench / 'outputs').relative_to(REPO))
    if subprocess.run(['git', '-C', str(REPO), 'status', '--porcelain', '--',
                       '.', f':!{own_log}'],
                      capture_output=True, text=True).stdout.strip():
        print('settle_item: arbol sucio; el veredicto no tendria commit', file=sys.stderr)
        return 2
    commit = subprocess.run(['git', '-C', str(REPO), 'rev-parse', '--short', 'HEAD'],
                            capture_output=True, text=True).stdout.strip()
    result = subprocess.run(row['verify'], shell=True, cwd=REPO,
                            capture_output=True, text=True)
    lines = [line for line in (result.stdout + result.stderr).splitlines()
             if line.strip() and not line.startswith('warning:')]
    tail = lines[-3:]
    append_log(workbench, {'kind': 'attempt', 'item': item, 'attempt': 0,
                           'model': 'conversational-session', 'outcome':
                           'success' if result.returncode == 0 else 'verify-failed',
                           'source': 'preexisting', 'verifyExit': result.returncode,
                           'commit': commit, 'verifyTail': tail})
    if result.returncode == 0:
        append_log(workbench, {'kind': 'accepted', 'item': item, 'commitExit': 0,
                               'commit': commit})
    print(f'{item}: verify={result.returncode} commit={commit} {tail[-1] if tail else ""}')
    return 0 if result.returncode == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
