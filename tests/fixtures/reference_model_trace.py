"""Ejecuta la rejilla de dominios con modelo en el ORM de la referencia.

Corre con el intérprete del entorno de referencia, en un proceso ``-I -B``
que sólo ve la raíz de ``odoo19c``: ni ``src/`` ni los settings de Django
(método de H-API-1089). La base es la desechable que
``scripts/workbench/reference-environment-isolated-20261106T071536/``
inicializa con el addon ``base`` de la referencia.

Uso: ``python -I -B reference_model_trace.py <raíz> <base> <data_dir>
<rejilla.py> <modelo> <su|user> [<contexto JSON>]``; imprime la traza
como JSON. El contexto (p. ej. ``{"tz": "America/Mexico_City"}``) es el
del ``Environment``; ``env.tz`` lo lee primero (``environments.py:286-294``).

``su`` ejecuta como ``SUPERUSER_ID`` (1): ``Environment.__new__`` fuerza
``su=True`` para ese uid (``odoo19c: odoo/orm/environments.py:64-67``).
``user`` ejecuta como el administrador sembrado por ``base`` (uid 2), sin
elevación. Los dos modos existen porque los optimizadores leen ``env.su``.
"""
import importlib.util
import json
import sys


SUPERUSER_ID = 1
ADMIN_ID = 2


def main(root, database, data_dir, grid_path, model_name, mode,
         context='{}'):
    sys.path.insert(0, root)
    # La raíz de la referencia sólo se conoce al ejecutar: los módulos se
    # resuelven después de añadirla, con llamadas y no con sentencias.
    importlib.import_module('odoo.tools').config['data_dir'] = data_dir
    Domain = importlib.import_module('odoo.orm.domains').Domain
    Environment = importlib.import_module('odoo.orm.environments').Environment
    Registry = importlib.import_module('odoo.orm.registry').Registry
    spec = importlib.util.spec_from_file_location('model_domain_grid',
                                                  grid_path)
    grid = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(grid)
    with Registry(database).cursor() as cursor:
        uid = SUPERUSER_ID if mode == 'su' else ADMIN_ID
        env = Environment(cursor, uid, json.loads(context))
        assert env.su == (mode == 'su'), (mode, env.su)
        lines = grid.trace(Domain, env[model_name], model_name)
        cursor.rollback()
    print(json.dumps(lines))


if __name__ == '__main__':
    main(*sys.argv[1:8])
