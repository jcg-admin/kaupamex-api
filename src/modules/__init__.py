"""Descubrimiento de addons y etapas delimitadas de su carga (TASK-API-0382).

``module.py`` resuelve raíces, manifests y dependencias externas;
``module_graph.py`` construye y ordena el grafo y prepara snapshots explícitos
por base. El catálogo persistido existe en ``base.IrModule``: su estado ya no
puede describirse como un mecanismo ausente o descartado.

``loading.py`` implementa load_data, load_demo, comprobación de nombres y
recuperación de estados. Todavía no ejecuta el ciclo completo de instalación,
actualización o eliminación. ``Registry.new`` prepara modelos del proceso
mediante _ensure_seeded y rechaza solicitudes que todavía no puede ejecutar,
antes de sustituir el registro anterior. La composición efectiva por base,
hooks y finalización de versiones siguen pendientes.
``INSTALLED_APPS`` y las migraciones Django no acreditan esa equivalencia.

El análisis histórico H-API-230 separó el algoritmo auto_install de su
persistencia; el catálogo persistido y los snapshots posteriores amplían ese
estado inicial. H-API-231 identificó mecanismos Django para migraciones de
esquema/datos: la equivalencia del ciclo pre/post/end y su disparo por versión
debe verificarse en el cargador efectivo, sin reimplementar Django.

Se conservan tres grafos con responsabilidades distintas:

- Dependencias de código de addons: manifests y ModuleGraph.
- Imports Python: scripts/check_addon_cycles.py.
- Módulos comerciales L0: authz.declaration.ModuleSpec.depends.

La cobertura por archivo y los contratos todavía no aceptados viven en el banco
odoo-orm-reference-inventory-20260910T181517. Esta descripción no sustituye sus
verificadores ni declara aceptación integral del sistema de módulos.
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
