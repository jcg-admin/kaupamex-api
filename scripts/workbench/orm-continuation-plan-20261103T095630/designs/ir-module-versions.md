# Versiones de `ir.module.module`: `latest_version`, `installed_version` y `published_version`

Sucesora de `designs/ir-module-dependency-module-id.md`. TASK-API-0397.

## Contrato medido en la referencia

`odoo19c: odoo/addons/base/models/ir_module.py`:

- `:285-288` el comentario *«attention: Incorrect field names !!
  installed_version refers the latest version (the one on disk);
  latest_version refers the installed version (the one in database);
  published_version refers the version available on the repository»*.
- `:289` `installed_version = fields.Char('Latest Version', compute='_get_latest_version')`.
- `:290` `latest_version = fields.Char('Installed Version', readonly=True)` (columna).
- `:291` `published_version = fields.Char('Published Version', readonly=True)` (columna).
- `:211-215` `_get_latest_version` (`@api.depends('name')`) asigna
  `installed_version` desde el manifiesto.

Consumidores en la fuente: `odoo19c: odoo/modules/module_graph.py:286` lee
`latest_version AS installed_version`; `odoo19c: odoo/modules/loading.py:269`
escribe `{'state': 'installed', 'latest_version': ver}`.

## Lo que el puerto tenía y diverge

El puerto persiste lo instalado en una columna `installed_version` (lo que la
fuente llama `latest_version`), no declara `published_version`, y su
`_get_latest_version` es un getter que devuelve la versión del manifiesto en
vez de asignar el campo calculado.

Medido (`grep installed_version` en `src/` y `addons/`): ningún código del
puerto escribe el valor instalado; el escritor de la fuente
(`loading.py:269`) no tiene contraparte todavía. Los lectores son
`module_graph.py:160` y el serializador del catálogo.

## Lo que esta unidad hace

- La columna persistida pasa a `latest_version` (migración con
  `RenameField`, que renombra la columna): mismo dato, nombre de la fuente.
- `installed_version` se declara calculado, sin columna, por
  `_get_latest_version` con `@api.depends('name')`, verbatim.
- `published_version` se declara como `Char` persistido (`AddField`).
- `module_graph._update_from_database` lee `latest_version` como la fuente.

## Decisión de compatibilidad, declarada

`addons/base/controllers/module_catalogue.py` publica en su contrato HTTP la
clave `installed_version` con el valor **persistido** (lo instalado). Tras la
unidad ese dato vive en `latest_version`. El contrato no cambia de
significado: la clave `installed_version` del serializador pasa a leer
`source='latest_version'`. Cambiar el valor que publica la clave sería una
ruptura del contrato HTTP y no es parte del porte.

## Pruebas (RED)

`tests/unit/base/test_ir_module_versions.py`: la columna `latest_version`,
`installed_version` calculado desde el manifiesto, `published_version`, y la
lectura del grafo.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrModule.installed_version` (calculado, sin columna) y `IrModule.latest_version` (columna) | `src/addons/base/models/ir_module.py` | `odoo19c: odoo/addons/base/models/ir_module.py:285-290` |
| `IrModule.published_version` | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:291` |
| `IrModule._get_latest_version`: asigna `installed_version` (`@api.depends('name')`) | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:211-215` |
| docstring de `IrModule`: cobertura medida 24 de 31 | ídem | `odoo19c: odoo/addons/base/models/ir_module.py:158-330` |
| migración `0156_ir_module_versions`: `RenameField` de la columna y `AddField` | `src/addons/base/migrations/0156_ir_module_versions.py` | `odoo19c: odoo/addons/base/models/ir_module.py:290-291` |
| `ModuleGraph._update_from_database`: lee `latest_version` | `src/modules/module_graph.py` | `odoo19c: odoo/modules/module_graph.py:286` |
| `TechnicalModuleSerializer.installed_version`: `source='latest_version'` | `src/addons/base/controllers/module_catalogue.py` | `odoo19c: odoo/addons/base/models/ir_module.py:285-290` |

Pruebas: `tests/unit/base/test_ir_module_versions.py` (3 casos; RED 3 de 3).
Consumidores corregidos: `test_ir_module_manifest.py` (lee el campo
calculado en vez de llamar al método), `test_module_catalog_database.py`,
`test_module_catalogue_api.py` y `test_module_graph_database.py` (escriben
`latest_version`), y el estado fabricado de
`test_module_category_migration.py`, que reconstruye el modelo previo a 0090
y ahora devuelve el nombre previo a 0156.

Anulación (copias restauradas y comparadas con `cmp`), dos piezas en una
ejecución con casos disjuntos: con `installed_version` fijo a `False` caen
exactamente los tres casos que leen el cálculo; sin `source='latest_version'`
en el serializador cae exactamente el caso del contrato del catálogo
(4 de 34).
