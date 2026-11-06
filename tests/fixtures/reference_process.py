"""El ORM de la referencia en un proceso aparte, con su propio intérprete.

Los contratos con modelo (``optimize`` con campos, los optimizadores por tipo,
``_as_predicate``) sólo se comparan ejecutando el ORM real de ``odoo19c``,
que necesita un ``Registry`` sobre una base con el addon ``base``. Ese ORM no
se carga en el proceso de la prueba: corre en el entorno de referencia que
construye ``scripts/workbench/reference-environment-isolated-20261106T071536/``
(TASK-API-0498), en un subproceso ``-I -B`` que no ve ``src/`` ni los
settings de Django — el aislamiento que H-API-1089 exige para no medir los
parches propios.

Tres variables lo localizan:

- ``CONTRACT_REFERENCE_PYTHON`` — el intérprete del entorno de referencia;
- ``CONTRACT_REFERENCE_DATABASE`` — la base inicializada con ``base``;
- ``CONTRACT_REFERENCE_DATA_DIR`` — el ``data_dir`` de esa inicialización.

Si falta alguna, la prueba se omite con el motivo; con
``CONTRACT_REFERENCE_REQUIRED=1`` **falla**, igual que la marca
``reference`` cuando falta el árbol (``reference_tree``).

Las credenciales de PostgreSQL viajan por el entorno del subproceso
(``PGUSER``/``PGPASSWORD``/``PGHOST``/``PGPORT``) desde
``settings.DATABASES['default']``; no se escriben en la línea de comando.
"""
import json
import os
import pathlib
import subprocess

import pytest
from django.conf import settings

from tests.fixtures import reference_tree

VARIABLES = ('CONTRACT_REFERENCE_PYTHON', 'CONTRACT_REFERENCE_DATABASE',
             'CONTRACT_REFERENCE_DATA_DIR')
DRIVER = pathlib.Path(__file__).with_name('reference_model_trace.py')
#: Una rejilla de un modelo tarda segundos; el tope sólo corta un bloqueo.
TIMEOUT = 600


def missing_reason():
    """El motivo de no poder ejecutar la referencia, o ``None``."""
    tree = reference_tree.missing_reason(reference_tree.reference_root())
    if tree is not None:
        return tree
    absent = [name for name in VARIABLES if not os.environ.get(name)]
    if absent:
        return f'entorno de referencia sin declarar: {", ".join(absent)}'
    python = pathlib.Path(os.environ['CONTRACT_REFERENCE_PYTHON'])
    if not python.is_file():
        return f'intérprete de referencia ausente: {python}'
    return None


def require():
    """Omite o falla la prueba si el proceso de referencia no está."""
    reason = missing_reason()
    if reason is None:
        return
    if reference_tree.reference_required():
        pytest.fail(f'{reason}; {reference_tree.REQUIRED_ENV}=1 exige la '
                    'referencia', pytrace=False)
    pytest.skip(reason)


def _database_environment():
    database = settings.DATABASES['default']
    pairs = (('PGUSER', 'USER'), ('PGPASSWORD', 'PASSWORD'),
             ('PGHOST', 'HOST'), ('PGPORT', 'PORT'))
    return {variable: str(database[key]) for variable, key in pairs
            if database.get(key)}


def trace(grid_path, model_name, mode, context=None):
    """La traza de ``grid_path`` sobre ``model_name`` en la referencia.

    ``mode`` es ``'su'`` o ``'user'`` (ver ``reference_model_trace``);
    ``context`` es el del ``Environment`` de la referencia.
    """
    environment = {'PATH': os.environ['PATH'],
                   'PYTHONDONTWRITEBYTECODE': '1',
                   **_database_environment()}
    command = [os.environ['CONTRACT_REFERENCE_PYTHON'], '-I', '-B',
               str(DRIVER), str(reference_tree.reference_root()),
               os.environ['CONTRACT_REFERENCE_DATABASE'],
               os.environ['CONTRACT_REFERENCE_DATA_DIR'], str(grid_path),
               model_name, mode, json.dumps(context or {})]
    done = subprocess.run(command, capture_output=True, text=True,
                          env=environment, timeout=TIMEOUT, check=False)
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout)
