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
