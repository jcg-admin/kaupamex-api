# `parent_path` de `ir.ui.menu` y `_check_parent_path`

Referencia: `odoo-tools@abe4040ec1a45beee90fb694e4eae4453e46b389`, Odoo 19 Community.

## Contrato de la referencia

- `odoo/orm/models.py:3255-3260` — `BaseModel._check_parent_path`: sin campo
  `parent_path` registra *"add a field parent_path on model %r: `parent_path =
  fields.Char(index=True)`."*; con el campo sin índice, *"parent_path field on
  model %r should be indexed! Add index=True to the field definition."*. Lo
  llama `_auto_init` para todo modelo con `_parent_store` (`:3214`).
- `odoo/addons/base/models/ir_ui_menu.py:20,28` — `ir.ui.menu` declara
  `_parent_store = True` y `parent_path = fields.Char(index=True)`.
- `child_of`/`parent_of` sobre un modelo con `_parent_store` se resuelven por
  `parent_path` (`=like` del prefijo).

## Medición (sonda ejecutada)

- Modelos con `_parent_store` en el árbol cargado: seis. Cinco con
  `parent_path`; `ir.ui.menu` **sin** el campo.
- `ir.ui.menu` con `[('id', 'child_of', X)]` o `[('parent', 'child_of', X)]`:
  `FieldError: Cannot resolve keyword 'parent_path'` — el traductor de
  dominios (`src/orm/domains.py:2853,2893`) confía en la bandera.
- La tabla de divergencias de `ir_ui_menu.py` decía *"parent_path no se porta
  — Django no lo tiene"*, y el docstring de la clase decía que `save()` lo
  mantiene. Las dos son falsas: el árbol ya lo mantiene en cinco modelos.
- `fields.Char(index=True)` en `test_orm.category` deja `index=True` en el
  campo pero no crea índice en la base: lo crea `Registry.check_indexes`, que
  sólo corre en `init_models`, no en las migraciones.

## Diseño

- `ir.ui.menu`: `parent_path` como `fields.Char(index=True, db_index=True)`
  con migración, mantenido en `save()`: al crear, el propio prefijo; al
  cambiar de padre, `_parent_store_update` de `orm.models` (REUSE: el mismo
  `UPDATE` de la fuente, `:5020-5054`, ya portado para BaseModel), con su
  rechazo de recursión.
- `_check_parent_path`: método de `RecordLoaderMixin` (lo heredan BaseModel y
  los 348 modelos de Django que lo adoptan, entre ellos los seis), con los dos
  mensajes verbatim. Hogar del llamador: `check()` de Django, que es el punto
  donde este árbol valida un modelo al cargar (el `_auto_init` de la
  referencia no tiene receptor: el DDL lo emiten las migraciones). Devuelve
  `checks.Error`; la referencia sólo registra en el log. **Divergencia
  declarada**: aquí bloquea `manage.py check`, porque un `_parent_store` sin
  columna rompe `child_of` en tiempo de ejecución.
- Índice: cuenta `field.index` (el atributo que la referencia consulta) o
  `db_index`.

## Controles de anulación previstos

- Sin `parent_path` en el menú: caen el caso `child_of` y el check del menú.
- Sin el llamador en `check()`: cae sólo el caso del check.
- Sin `_parent_store_update` en `save()`: cae sólo el caso de reparentar.
