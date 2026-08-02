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
``loading.py`` (632)         **NO** — el orden de carga lo da ``INSTALLED_APPS``
                             + ``django.apps``
``db.py`` (200)              **PARCIAL** — su *algoritmo* de ``auto_install`` SÍ
                             (→ ``ModuleGraph.auto_installable``); su
                             *almacenamiento* (``ir_module_module``) no
``migration.py`` (253)       **pendiente de decidir** — ver abajo
``neutralize.py`` (41)       **NO** — depende de ``loading``
===========================  ==========================================================

La decisión de no adoptar el install dinámico no es de este pase: viene de
``analisis-organizacion-addon-odoo-modules`` ("Qué NO se adopta"), y se sostiene
porque su premisa —módulos de terceros con set de instalación por cliente— no es
la de este árbol.

**Corrección de un descarte apresurado (H-API-230).** La primera versión de este
docstring decía ``db.py`` → **NO**, "es el estado de ``ir_module_module``". Era
falso por omisión: ``db.py:91-124`` **implementa ``auto_install``** —un bucle de
punto fijo que marca los addons auto-instalables cuyas dependencias requeridas
ya están— y ése es justo el mecanismo por el que la referencia instala solos los
puentes ``_portal``/``_signup``. Descartarlo contradecía la razón por la que se
estaba portando el manifest. El algoritmo es de **grafo** y se portó; lo que no
se porta es la tabla donde Odoo lo persiste.

**``migration.py`` no está resuelto.** Su convención —scripts ``pre-``/``post-``/
``end-`` bajo ``<addon>/migrations/<version>/``, ejecutados antes y después de la
inicialización del módulo, y ``end-`` tras **todos**— no tiene equivalente en
Django: ``RunPython`` es schema-first y no conoce ni versión de addon ni fase
``end-``. Decir "lo hacen las migraciones de Django" era una equivalencia sin
medir. Queda como pregunta abierta contra la iniciativa
``consolidar-migraciones-django-squash``, no como descarte.

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
