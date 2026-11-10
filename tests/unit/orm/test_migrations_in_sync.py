"""Los modelos y las migraciones están en sincronía.

La referencia lleva el esquema a los campos declarados en cada instalación
(``odoo19c: odoo/orm/models.py:3170-3248`` ``_auto_init``, y
``:3109-3136`` ``_check_removed_columns``). Aquí esa autoridad son las
migraciones de Django, y la equivalencia sólo vale si ningún cambio de modelo
queda sin migración: es lo que esta prueba exige (TASK-API-0515). Diseño en
``designs/schema-and-translation-symbols-decision.md`` del Workbench.

Corre en un proceso aparte, como ``manage.py makemigrations --check``: en el
proceso de pytest los módulos de prueba registran modelos de sondeo en
``apps`` (``CacheProbe``, ``ComputeDispatchProbe``…), y el autodetector los
contaría como cambios sin migración.

*Métrica:* lo que ``makemigrations --check --dry-run`` propone sobre el
registro que Django carga.
*Ciega a:* migraciones escritas a mano que divergen del modelo sin que el
autodetector lo note (``RunSQL``), a modelos que ningún ``models/__init__``
importa, y al estado real de una base ya existente.
"""
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[3]


def test_no_model_change_is_left_without_a_migration():
    environment = dict(os.environ,
                       DJANGO_SETTINGS_MODULE='config.settings.testing')
    result = subprocess.run(
        [sys.executable, 'src/manage.py', 'makemigrations', '--check',
         '--dry-run'],
        cwd=ROOT, env=environment, capture_output=True, text=True,
        check=False)
    assert result.returncode == 0, (
        'cambios de modelo sin migración:\n' + result.stdout
        + result.stderr)
