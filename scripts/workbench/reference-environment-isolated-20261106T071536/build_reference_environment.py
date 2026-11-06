"""Construye el entorno de referencia de odoo19c fuera del Consumer.

Y prueba su carga.

Separación que este script materializa (TASK-API-0498):

- **Entorno de referencia.** Un venv desechable fuera del repositorio,
  instalado desde el ``requirements.txt`` que odoo19c declara para sí mismo.
  Sólo carga código de ``odoo-tools``; no ve ``src/`` ni los settings de
  Django (método de H-API-1089: proceso aislado de los parches del Consumer).
- **Entorno del Consumer.** ``pyproject.toml`` y ``uv.lock`` sin cambios; el
  código de producción no importa ``odoo``.

Dos sustituciones sobre el ``requirements.txt`` de la referencia, declaradas en
``record.json``:

- ``python-ldap`` se retira: compila contra ``lber.h`` y el contenedor no trae
  las cabeceras de OpenLDAP. Sólo lo usa el addon ``auth_ldap``; el ORM no lo
  importa.
- ``psycopg2==2.9.10`` se sustituye por ``psycopg2-binary==2.9.10``: el mismo
  paquete en rueda precompilada, porque la compilación exige ``libpq-fe.h``.

Uso::

    python3 build_reference_environment.py <venv> <salida>

No escribe en ``odoo-tools``: el intérprete corre con ``-B`` y
``PYTHONDONTWRITEBYTECODE=1``, y el registro incluye ``git status`` de
``odoo-tools`` antes y después.
"""
import json
import os
import pathlib
import subprocess
import sys

TOOLS_ROOT = pathlib.Path('/home/user/odoo-tools')
REFERENCE_ROOT = TOOLS_ROOT / '19.x/odoo-19.0/odoo-19.0/odoo-19.0'
REMOVED = ('python-ldap',)
REPLACED = {'psycopg2==2.9.10 ': 'psycopg2-binary==2.9.10 '}
LOAD_PROBE = (
    'import sys, json\n'
    'sys.path.insert(0, sys.argv[1])\n'
    'import odoo\n'
    'from odoo.orm import models, fields, domains, environments, registry\n'
    'print(json.dumps({"version": odoo.release.version,\n'
    '  "odoo_modules": sorted(m for m in sys.modules'
    ' if m.startswith("odoo")),\n'
    '  "django_loaded": "django" in sys.modules,\n'
    '  "werkzeug_loaded": "werkzeug" in sys.modules}))'
    '\n'
)


def run(command, **kwargs):
    """Ejecuta ``command`` y devuelve código, salida y error."""
    done = subprocess.run(command, capture_output=True, text=True, **kwargs)
    return {'command': command, 'exit': done.returncode,
            'stdout': done.stdout, 'stderr': done.stderr}


def derived_requirements(target):
    """Escribe el requirements de la referencia con las dos sustituciones."""
    lines = []
    for line in (REFERENCE_ROOT / 'requirements.txt').read_text().splitlines():
        if line.lower().startswith(REMOVED):
            continue
        for old, new in REPLACED.items():
            if line.startswith(old):
                line = new + line[len(old):]
        lines.append(line)
    target.write_text('\n'.join(lines) + '\n')


def load_probe(python):
    """Carga ``odoo.orm`` con ``python`` en un proceso aislado."""
    env = {'PATH': os.environ['PATH'], 'PYTHONDONTWRITEBYTECODE': '1'}
    return run([python, '-I', '-B', '-c', LOAD_PROBE, str(REFERENCE_ROOT)],
               env=env)


def main(venv, out):
    """Construye el venv, carga la referencia y registra la procedencia."""
    venv, out = pathlib.Path(venv), pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    requirements = out / 'reference-requirements.txt'
    derived_requirements(requirements)
    status_before = run(['git', '-C', str(TOOLS_ROOT), 'status',
                         '--porcelain'])
    steps = []
    if not (venv / 'bin' / 'python').exists():
        steps.append(run(['uv', 'venv', '-q', '--python', sys.executable,
                          str(venv)]))
    steps.append(run(['uv', 'pip', 'install', '-q', '-r', str(requirements)],
                     env={**os.environ, 'VIRTUAL_ENV': str(venv)}))
    freeze = run(['uv', 'pip', 'freeze'],
                 env={**os.environ, 'VIRTUAL_ENV': str(venv)})
    (out / 'reference-freeze.txt').write_text(freeze['stdout'])
    reference = load_probe(str(venv / 'bin' / 'python'))
    consumer = load_probe(str(pathlib.Path.cwd() / '.venv' / 'bin' / 'python'))
    record = {
        'reference_revision': run(['git', '-C', str(TOOLS_ROOT), 'rev-parse',
                                   'HEAD'])['stdout'].strip(),
        'removed': list(REMOVED),
        'replaced': REPLACED,
        'install_exits': [step['exit'] for step in steps],
        'reference_load': {'exit': reference['exit'],
                           'result': (json.loads(reference['stdout'])
                                      if reference['exit'] == 0 else None),
                           'stderr_tail': reference['stderr'][-600:]},
        'consumer_load_control': {'exit': consumer['exit'],
                                  'stderr_tail': consumer['stderr'][-600:]},
        'tools_status_before': status_before['stdout'],
        'tools_status_after': run(['git', '-C', str(TOOLS_ROOT), 'status',
                                   '--porcelain'])['stdout'],
    }
    (out / 'record.json').write_text(json.dumps(record, indent=2,
                                                ensure_ascii=False) + '\n')
    ok = (reference['exit'] == 0 and consumer['exit'] != 0
          and not record['tools_status_after'])
    print(json.dumps({'reference_exit': reference['exit'],
                      'consumer_exit': consumer['exit'], 'ok': ok}))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
