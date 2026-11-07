"""Crea la base desechable de la referencia e instala ``base`` u otros addons.

Los diferenciales con modelo (``tests/fixtures/reference_process.py``)
necesitan un ``Registry`` real de ``odoo19c``, y ese registro no se monta sin
``ir.model`` y el resto de ``base``: medido, un registro con sólo modelos
propios rehúsa con ``KeyError: 'ir.model'`` en ``setup_model_classes``.

La base se crea con el rol de QA de ``src/.env`` (``CREATEDB``), con nombre
``orm_refproc_<sufijo>``; la inicialización corre ``odoo.cli.main`` con el
intérprete del entorno de referencia, en un proceso ``-I -B`` y con
``--data-dir`` fuera del repositorio. Las credenciales viajan por
``PGUSER``/``PGPASSWORD``/``PGHOST``/``PGPORT``, nunca por la línea de
comando, y no se escriben en el registro.

Uso::

    .venv/bin/python initialize_reference_database.py <python de referencia>
        <base> <data_dir> <salida> [<módulos>]

``<módulos>`` es la lista separada por comas que recibe ``-i``; por omisión,
``base``. Con ``test_orm`` la base trae los modelos de prueba de la fuente
(``odoo19c: odoo/addons/test_orm``), que dependen de ``web`` y ``web_tour``;
por eso la ruta de addons incluye las dos raíces del árbol.

Al terminar imprime las tres variables que ``reference_process`` lee.
"""
import json
import os
import pathlib
import subprocess
import sys

import psycopg
from decouple import Config, RepositoryEnv

ROOT = pathlib.Path(__file__).resolve().parents[3]
REFERENCE_ROOT = pathlib.Path(
    '/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0')
PREFIX = 'orm_refproc_'
ADDONS_PATH = ','.join(str(REFERENCE_ROOT / part)
                       for part in ('odoo/addons', 'addons'))
#: La instalación de ``base`` tardó menos de dos minutos; el tope corta un
#: bloqueo, no una ejecución lenta.
INIT_BUDGET = 1800
CLI = ('import sys; sys.path.insert(0, sys.argv.pop(1)); '
       'import odoo.cli; odoo.cli.main()')


def database_environment(config):
    """Las variables de libpq con el rol de QA, para el subproceso."""
    pairs = (('PGUSER', 'DB_QA_USER'), ('PGPASSWORD', 'DB_QA_PASSWORD'),
             ('PGHOST', 'DB_QA_HOST'), ('PGPORT', 'DB_QA_PORT'))
    return {variable: config(key) for variable, key in pairs
            if config(key, default='')}


def create_database(environment, name):
    """Crea ``name`` si no existe; devuelve si la creó."""
    with psycopg.connect(dbname='postgres', autocommit=True,
                         host=environment.get('PGHOST'),
                         port=environment.get('PGPORT'),
                         user=environment['PGUSER'],
                         password=environment['PGPASSWORD']) as connection:
        exists = connection.execute(
            'SELECT 1 FROM pg_database WHERE datname = %s', [name]).fetchone()
        if not exists:
            connection.execute(f'CREATE DATABASE "{name}"')
        return not exists


def main(python, name, data_dir, out, modules='base'):
    """Crea la base, instala ``modules`` y registra el resultado."""
    assert name.startswith(PREFIX), f'la base debe empezar por {PREFIX}'
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    config = Config(RepositoryEnv(ROOT / 'src' / '.env'))
    environment = database_environment(config)
    created = create_database(environment, name)
    log = out / 'initialize-base.log'
    with log.open('w') as handle:
        done = subprocess.run(
            [python, '-I', '-B', '-c', CLI, str(REFERENCE_ROOT), '-d', name,
             '-i', modules, '--stop-after-init', '--without-demo=all',
             '--data-dir', data_dir, f'--addons-path={ADDONS_PATH}'],
            stdout=handle, stderr=subprocess.STDOUT, timeout=INIT_BUDGET,
            env={'PATH': os.environ['PATH'], 'PYTHONDONTWRITEBYTECODE': '1',
                 **environment}, check=False)
    record = {'database': name, 'created': created, 'modules': modules,
              'init_exit': done.returncode,
              'log_errors': sum(1 for line in log.read_text().splitlines()
                                if ' ERROR ' in line or 'Traceback' in line)}
    (out / 'initialize-record.json').write_text(
        json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))
    if done.returncode == 0:
        print(f'export CONTRACT_REFERENCE_PYTHON={python}')
        print(f'export CONTRACT_REFERENCE_DATABASE={name}')
        print(f'export CONTRACT_REFERENCE_DATA_DIR={data_dir}')
    return done.returncode


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:6]))
