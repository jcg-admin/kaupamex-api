"""Settings de MEDICIÓN — ``testing`` sin el addon que otro agente reescribe.

No es configuración del producto: vive en ``scripts/evidence/`` porque su
única razón es poder medir esta tarea (#287, ``html_editor``) mientras otro
agente (#281) tiene ``addons/base_install_request`` a medio reescribir.

Qué desbloquea, medido 2026-09-02: ``setup_databases`` serializa la base
entera al montarla —``serialized_aliases=None`` en ``pytest_django
/fixtures.py:140``, así que **no se puede apagar desde los settings**— y esa
serialización hace un ``SELECT`` sobre todos los modelos registrados. El
modelo en vuelo declara ``db_column='module_id'`` y la tabla tiene
``module_id_id``, así que el ``SELECT`` revienta y **toda** la sesión muere en
setup, incluidos los 103 casos que no tocan ese addon:

    psycopg.errors.UndefinedColumn: column
    base_module_install_request.module_id does not exist
    HINT: Perhaps you meant to reference "…module_id_id".

Retirar el addon de ``INSTALLED_APPS`` para la medición no cambia nada de lo
que estos casos miden: ``html_editor`` no lo declara en su ``depends`` ni lo
importa. Se retira **este archivo** en cuanto el árbol de #281 vuelva a ser
coherente.
"""
from config.settings.testing import *  # noqa: F401,F403
from config.settings.testing import INSTALLED_APPS as _INSTALLED_APPS

INSTALLED_APPS = [app for app in _INSTALLED_APPS
                  if not app.endswith('base_install_request')]
