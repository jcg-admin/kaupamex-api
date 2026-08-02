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
``migration.py`` (253)       **NO** — resuelto 2026-08-02; ver abajo
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

**``migration.py`` — resuelto: NO se porta (H-API-231, 2026-08-02).** Medido
contra la referencia completa (253 loc): su disparador es
``pkg.load_state == 'to upgrade'`` leído de ``ir_module_module``
(``migration.py:134,151``; ``module_graph.py:158,309``) — el mismo
almacenamiento que H-API-230 delimitó como no-portable, y aquí sin algoritmo
separable: la selección de scripts depende de ``load_version`` de la BD. Su
función (data ops alrededor del schema sync) la cubren ``RunPython``/``RunSQL``
— en uso hoy (2 seeds: ``authz_password_policy/0001``, ``authz_signup/0001``) y
con precedente PROVEN de que el squash las preserva (DEC-MIG-2). Los dos huecos
residuales (fase ``end-`` dedicada; ``0.0.0`` re-ejecutable) tienen expresión
Django (``dependencies``/``run_before``; management command) y 0 demandantes.
Análisis completo:
``docs: gestion/pm/api/iniciativas/consolidar-migraciones-django-squash/
analisis-mecanismo-migracion-odoo-vs-django.rst``.

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
