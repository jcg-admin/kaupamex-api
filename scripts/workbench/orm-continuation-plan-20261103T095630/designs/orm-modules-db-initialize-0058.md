# TASK-GEN-0058 — `is_initialized` / `initialize` y la normalización de `_load_manifest`

Fuente: `odoo19c: odoo/modules/db.py:17-124` (`_logger`, `is_initialized`,
`initialize`) y `odoo19c: odoo/modules/module.py:415-467` (`_load_manifest`).
Investigación previa: borrador `research/orm-modules-db-initialize-0058.md`
(scratchpad), con la decisión del orquestador del 2026-11-25.

## Por qué `_load_manifest` entra en esta unidad

`initialize` lee `auto_install` **normalizado** (`db.py:82`:
`auto_install_required = d in (info['auto_install'] or ())`). La fuente lo
normaliza en `_load_manifest` (`module.py:445-458`): un iterable pasa a
`set` y tiene que ser subconjunto de `depends`; `True` pasa a `set(depends)`.
El `_load_manifest` del puerto (`src/modules/module.py:165-177`) no lo hace,
así que con `auto_install: True` el `in` de `db.py:82` sería `d in True` →
`TypeError`. Es precondición, no adorno. Búsqueda previa en el store de
tareas: `buscar-tareas --query _load_manifest` → 0 de 2678; ninguna unidad del
plan lo posee. Se porta entero (`porte-completo-no-parcial.md`).

Medido sobre los 124 manifests de `addons/` y `src/addons/` (2026-11-25):
ningún addon salvo `base` trae `depends` vacío y `base` declara `[]`; los 124
declaran `license`; 35 no declaran `author`; 16 declaran `auto_install`, los 16
como `True`, y ninguno lista una no-dependencia. El único cambio de forma
observable es `True` → `set(depends)`.

## Contrato por símbolo

| Símbolo | Veredicto |
|---|---|
| `module._load_manifest`: `deepcopy` del default (`:421`) | portar |
| `author` ausente → contributors / maintainer / `''` + aviso (`:424-430`) | **divergencia declarada, se conserva**: aquí se deriva de `release.author` porque todos los addons son first-party |
| `license` ausente → `LGPL-3` + aviso (`:432-434`) | portar |
| `depends`: `base` → `[]`; vacío → `['base']` (`:436-440`) | portar |
| `auto_install`: iterable → `set` con aserción de subconjunto; `True` → `set(depends)` (`:445-458`) | portar |
| versión inválida → `ValueError` si `installable`; incompatible → `installable=False` + aviso (`:460-466`) | portar |
| `db._logger` (`:17`) | portar |
| `db.is_initialized(cr)` (`:20-26`) | portar fiel: `table_exists(cr, 'ir_module_module')` (`src/tools/sql.py:426`) |
| `initialize` §a `base_data.sql` (`:37-45`) | **divergencia declarada**: el esquema lo crean las migraciones de `base`; `initialize` rehúsa con `RuntimeError` si `is_initialized` es falso, nombrando `migrate` |
| `initialize` §b filas + categoría (`:47-68`) | reutilización: `_refresh` de `update_module_list` se extrae a una función de servicio que comparten el comando e `initialize`. Divergencias de forma ya existentes: textos `Char`/`Text`, no JSON `en_US`; campo `web` ausente en `IrModule` |
| `initialize` §b `ir_model_data base.module_<name>` (`:72-76`) | portar, idempotente: la fuente corre sobre tablas vacías, aquí `initialize` puede reencontrar filas |
| `initialize` §b `auto_install_required` (`:77-83`) | portar en `_sync_dependencies` del servicio, que es su hogar |
| `initialize` §c `skip_auto_install` (`:85-89`) | parámetro keyword de `initialize`: la opción de configuración no existe en el puerto |
| `initialize` §d punto fijo SQL (`:91-124`) | portar el SQL verbatim |
| precondición de la fuente: `initialize` sólo corre con `is_initialized` falso (`loading.py:371-376`), así que su punto fijo nunca ve `installed` | portar como precondición: rehúsa (`UserError`) si alguna fila de `ir_module_module` está `installed`, sin cambiar ningún `state`. No se excluye `installed` del SQL: sería una divergencia que la fuente no tiene |

## Consumidores

- `modules.loading.load_modules` gana la guarda `is_initialized`: si es falso,
  registra error y retorna (`loading.py:371-373`). **No** llama `initialize`:
  esta base siempre está migrada e instalada cuando corre `post_migrate`.
- `reset_modules_state` sustituye `introspection.table_names` por
  `is_initialized`: una sola pregunta, una sola fuente.
- `orm/registry.py` (`partially_updated_database`, `registry.py:168-172`):
  fuera de alcance, declarado.

## Casos (RED), `tests/integration/base/test_modules_db_initialize.py`

1. `is_initialized` es verdadero sobre la base migrada.
2. `is_initialized` es falso con un `search_path` a un esquema vacío creado en
   la transacción (mide el SQL real, no un literal).
3. `initialize` crea las filas y la identidad `base.module_<name>` con
   `noupdate=True`, sin duplicarla en una segunda llamada.
4. `auto_install_required` es verdadero sólo para las dependencias listadas.
5. El punto fijo marca `to install` el puente cuyas dependencias requeridas lo
   están, y nunca un módulo `uninstallable`.
6. `skip_auto_install=True` deja sólo `base` en `to install`.
7. Con un módulo `installed`, `initialize` rehúsa y no cambia ningún `state`.

Y en `tests/unit/base/test_load_manifest.py`: `True` → `set(depends)`; lista →
`set`; lista con una no-dependencia → `AssertionError`; `depends` vacío →
`['base']`; versión incompatible → `installable=False`; sin `license` →
`LGPL-3`.

## Anulaciones previstas

- sin la normalización de `auto_install`: caen los casos de `_load_manifest`
  sobre `auto_install` y el 4;
- sin `_ensure_module_xmlids`: cae el 3;
- sin el punto fijo: cae el 5; sin la rama `skip`: cae el 6;
- sin la precondición de `installed`: cae el 7;
- `is_initialized` con `True` fijo: cae el 2.
