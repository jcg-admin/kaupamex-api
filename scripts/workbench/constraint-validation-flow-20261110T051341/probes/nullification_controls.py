"""Controles de anulación del porte de la validación de restricciones.

Cada caso de ``nullification_cases.json`` retira una pieza del porte
(reemplaza un texto único por otro), ejecuta el subconjunto de pruebas y
nombra las que caen; después restaura el contenido original. Un caso sin
pruebas caídas es un control que no discrimina y se investiga.

Uso, desde la raíz del repo::

    python3 scripts/workbench/constraint-validation-flow-20261110T051341/\\
probes/nullification_controls.py [nombre ...]

Escribe en el árbol de trabajo mientras corre: no se ejecuta durante un
gate.
"""
import json
import os
import pathlib
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
SPEC = json.loads((HERE / 'nullification_cases.json').read_text())


def run_case(case):
    path = pathlib.Path(case['path'])
    original = path.read_text()
    if original.count(case['old']) != 1:
        raise SystemExit(f"{case['name']}: el texto no es único")
    path.write_text(original.replace(case['old'], case['new']))
    try:
        for cache in pathlib.Path('src').rglob('__pycache__'):
            shutil.rmtree(cache, ignore_errors=True)
        env = dict(os.environ,
                   DJANGO_SETTINGS_MODULE='config.settings.testing',
                   PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run(
            ['uv', 'run', 'pytest', *SPEC['tests'], '-q', '--reuse-db',
             '-p', 'no:randomly', '-rf'],
            capture_output=True, text=True, env=env, timeout=600)
    finally:
        path.write_text(original)
    lines = result.stdout.strip().splitlines()
    fallen = [line.split('::', 1)[1].split(' ')[0] for line in lines
              if line.startswith(('FAILED', 'ERROR'))]
    print(f"== {case['name']}: {lines[-1] if lines else result.stderr[-200:]}")
    for name in fallen:
        print('   ', name)


def main(names):
    for case in SPEC['cases']:
        if not names or case['name'] in names:
            run_case(case)


if __name__ == '__main__':
    main(sys.argv[1:])
