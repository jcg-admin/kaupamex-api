"""``modules`` — fiel a ``odoo/modules/`` (Odoo 19).

Paquete del **sistema de módulos**: descubrir addons, leer y validar su
``__manifest__.py``, y resolver el grafo ``depends``.

Qué se porta y qué NO — declarado, no omitido en silencio
---------------------------------------------------------

===========================  ==========================================================
``odoo/modules/``            Aquí
===========================  ==========================================================
``module.py`` (623 loc)      **portado** → ``modules/module.py`` (manifest + descubrimiento)
``module_graph.py`` (317)    **portado** → ``modules/module_graph.py`` (grafo + orden)
``registry/`` (3 loc shim)   **portado** → ``modules/registry/`` (shim sobre ``orm.registry``)
``loading.py`` (632)         **NO** — lo hace ``INSTALLED_APPS`` + ``django.apps``
``migration.py`` (253)       **NO** — lo hacen las migraciones de Django
``db.py`` (200)              **NO** — es el estado de ``ir_module_module`` para el
                             *install dinámico por-BD*, que este proyecto no adopta
                             (los addons son first-party y se activan por
                             suscripción: ``CompanyModuleSubscription``)
``neutralize.py`` (41)       **NO** — depende de ``loading``
===========================  ==========================================================

La decisión de no adoptar el install dinámico no es de este pase: viene de
``analisis-organizacion-addon-odoo-modules`` ("Qué NO se adopta"), y se sostiene
porque su premisa —módulos de terceros con set de instalación por cliente— no es
la de este árbol.

**Tres grafos distintos, no uno** (H-API-228). Este paquete resuelve el
**primero**; los otros dos ya tienen dueño y no se colapsan aquí:

1. **addons-código** — ``__manifest__.py:depends``: qué addon necesita a qué
   addon. Es lo que ``module_graph`` resuelve.
2. **imports** — derivado con ``ast`` por ``scripts/check_addon_cycles.py``.
3. **módulos comerciales L0** — ``authz.declaration.ModuleSpec.depends``: qué
   módulo puede activarse para una company.
"""
from modules.module import (          # noqa: F401
    MANIFEST_NAMES,
    Manifest,
    MissingDependency,
    adapt_version,
    check_python_external_dependency,
    check_version,
    get_manifest,
    get_module_path,
    get_modules,
    get_modules_with_version,
    load_manifest,
)
from modules.module_graph import ModuleGraph, ModuleNode   # noqa: F401

__all__ = [
    'MANIFEST_NAMES', 'Manifest', 'MissingDependency', 'adapt_version',
    'check_python_external_dependency', 'check_version', 'get_manifest',
    'get_module_path', 'get_modules', 'get_modules_with_version',
    'load_manifest', 'ModuleGraph', 'ModuleNode',
]
