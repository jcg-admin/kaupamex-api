"""``/kpi/summary`` — el resumen de indicadores de un lote de bases.

Adaptación de ``odoo19c: addons/base_setup/controllers/kpi.py``
(``odoo-tools@622ddc2a``, LGPL-3 — copia + adaptación con atribución, DEC-KX-03;
mecanismo declarado: adaptación del fuente, no reimplementación).

Porte BLOQUEADO — 1 de 4 símbolos
==================================

Portado: ``_get_kpi_providers``. Bloqueados con su medición y su sucesor:
``_db_kpi_summary``, ``KpiController`` y su ruta ``kpi_summary``.

La medición del bloqueo
------------------------

.. code-block:: text

   grep -rn "def db_connect" --include=*.py src/ addons/ | wc -l
   → 0

   grep -rn "def all_addon_manifests" --include=*.py src/ addons/ | wc -l
   → 0

El acto central de este archivo es **conectarse a una base cuyo nombre llega
en la petición**, y hacerlo **sin autenticar** (``auth='none'``): la credencial
es la propia clave de API, que se valida ya dentro de la base contactada. Aquí
las dos mitades de eso chocan con una decisión de plataforma vigente:

- **El conjunto de bases alcanzables es cerrado.** ``ADR-021`` fija multi-base
  por *alias declarado* en ``settings.DATABASES`` (``company_<N>_db``, ver
  ``src/orm/routers.py:84-108``). No hay —ni debe haber— un conector que abra
  una base por nombre arbitrario: la enumeración de bases del servidor es
  justo lo que la fuente evita filtrar con su ``except psycopg2.Error``.
- **Una vista sin capacidad declarada salta DEC-11.** ``IsAuthenticated`` a
  secas ya está prohibido en este árbol; ``auth='none'`` lo está con más razón.
  Publicar la superficie exige decidir *qué* la gatea, y eso es alcance de
  plataforma, no de este porte.

``_check_apikey_credentials`` **sí** existe
(``src/addons/base/models/res_users.py:2836``) y ``release.series`` también
(``src/release.py:27``), así que lo que falta no es la credencial ni la
versión: es el conector y la decisión de exposición.

Divergencias declaradas
------------------------

- **``Manifest.all_addon_manifests()`` no existe como método de clase**, y no
  hace falta: aquí el barrido equivalente es ``get_modules()`` +
  ``get_manifest()`` (``src/modules/module.py:203,209``), que es literalmente
  lo que la fuente hace por dentro. La conducta portada es idéntica.
- **``@cache`` se conserva.** La fuente la justifica en su propio comentario —
  *"no need to call more than once per worker"*— y el argumento vale igual.
- **El paquete de importación** es ``addons.<nombre>`` y no
  ``odoo.addons.<nombre>``: es el prefijo de este árbol, no un cambio de
  mecanismo.

Lo que este archivo no cierra
==============================

Los tres símbolos bloqueados de arriba. Sucesor: tarea **#457**, que decide la
exposición del resumen de indicadores (gate y conjunto de bases alcanzables)
antes de portar el conector.
"""
import logging
from functools import cache
from importlib import import_module

from modules.module import get_manifest, get_modules

_logger = logging.getLogger(__name__)

#: La clave del manifest que declara los proveedores — la cadena de la fuente
#: (``odoo19c: :37``), verbatim.
KPI_PROVIDERS_KEY = 'kpi_providers'


@cache  # no need to call more than once per worker
def _get_kpi_providers():
    """≙ ``_get_kpi_providers`` (``odoo19c: kpi.py:20-70``).

    Docstring de la fuente, verbatim en lo que describe el contrato: *"Load KPI
    provider functions declared by addons from the addons path. This function
    scans all addon manifests for a ``kpi_providers`` entry, expected as a list
    of strings in the format ``'module.path:function'``, where `module.path` is
    relative to the addon and may be empty (':function')."*

    Devuelve una tupla —cacheada— de ternas
    ``(addon, kpi_provider, kpi_provider_fn)``. Sólo las funciones válidas y
    invocables salen; las entradas inválidas se registran en el log, como en la
    fuente.
    """
    kpi_providers = []
    for name in get_modules():
        manifest = get_manifest(name)
        if not manifest:
            continue
        # kpi_providers should be a list of strings in the form
        # 'pkg.module:function' where 'pkg.module' is relative to the addon and
        # can be empty
        for kpi_provider in manifest.get(KPI_PROVIDERS_KEY, []):
            module_path, colon, function = kpi_provider.partition(':')
            if module_path.startswith('.') or not colon:
                _logger.warning(
                    "Invalid KPI provider hook path %r in addon %r. "
                    "Expected formats are 'pkg.module:function' or ':function'.",
                    kpi_provider, name)
                continue

            try:
                if module_path:
                    # Support "submodule.path:function"
                    module = import_module(f'.{module_path}',
                                           package=f'addons.{name}')
                else:
                    # Support ":function" for root-level function
                    module = import_module(f'addons.{name}')
                if not function:
                    _logger.warning(
                        'KPI provider %r from addon %r has an empty function '
                        'name.', kpi_provider, name)
                    continue
                provider = getattr(module, function)
            except Exception:
                _logger.exception(
                    'Failed to import KPI provider %r from addon %r.',
                    kpi_provider, name)
                continue

            if not callable(provider):
                _logger.warning(
                    'KPI provider %r from addon %r is not callable.',
                    kpi_provider, name)
                continue

            kpi_providers.append((name, kpi_provider, provider))

    return tuple(kpi_providers)
