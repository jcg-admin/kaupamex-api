# Restricciones de `ir.actions.*` como `@api.constrains` del ORM (4d)

TASK-API-0397. Depende de `ir-actions-bindings-0397`.

## Contrato medido en la referencia

`odoo19c: odoo/addons/base/models/ir_actions.py:81-103`:

- `@api.constrains('path')`: corre en `create` y en `write` del ORM, no al
  validar un formulario.
- Cuatro rechazos con los mensajes de la fuente, traducidos con `_`: el
  patrón `[a-z][a-z0-9_-]*`, los prefijos `m-` y `action-`, y la palabra
  `new` por igualdad.
- **Unicidad entre tablas**: `search_count([('path', '=', action.path)]) > 1`
  sobre `ir.actions.actions`. El comentario de la fuente (`:94-101`) lo
  justifica: las tablas de los subtipos heredan de `ir_actions` y un índice
  único sólo vale dentro de su tabla, así que `_path_unique` (`:62-65`)
  cubre una tabla y el `search_count` cubre la familia.

`odoo19c: odoo/addons/base/models/ir_actions.py:270-276` (`_check_model`,
`@api.constrains('res_model', 'binding_model_id')`): `res_model` y
`binding_model_id.model` deben estar en `self.env`.

`odoo19c: odoo/addons/base/models/ir_actions.py:300-307`
(`_check_view_mode`, `@api.constrains('view_mode')`): modos repetidos, y
`' ' in modes`. Es pertenencia en la **lista**: rechaza un modo que sea
exactamente un espacio, no un modo que contenga uno. `'list, form'` pasa en
la fuente.

## Estado del árbol (medido)

- Los cuatro rechazos viven en `IrActionsBase.clean`
  (`src/addons/base/models/ir_actions.py:573-602`), con mensajes en español
  y tres constantes de módulo (`PATH_PATTERN`, `RESERVED_PATH_PREFIXES`,
  `RESERVED_PATH_WORD`, `:245-253`) que la fuente no declara; su único
  consumidor es ese `clean`.
- `clean` no lo llama `create` ni `write` de `BaseModel`; sólo las pruebas
  (`tests/integration/base/test_ir_actions_constraints.py`, `TestCheckPath`)
  lo invocan sobre instancias sin guardar.
- `_check_model` y `_check_view_mode` viven en `IrActionsActWindow.clean`
  (`:825-868`), en español, y la segunda **difiere**:
  `any(' ' in mode for mode in modes)` rechaza `'list, form'`, que la fuente
  admite. Su docstring lo presenta como mejora («rechazar el espacio es más
  útil»); es una divergencia sin decisión registrada.
- La unicidad entre tablas falta: 0 llamadas a `search_count` sobre `path`.
- Desde 4a los seis modelos de acción son `BaseModel`, cuyo `create` y
  `write` ejecutan `_validate_fields` (`src/orm/models.py:1292,3273`).
- `exceptions.ValidationError` es la de Django (`src/exceptions.py:27`).

## Cambio

1. `IrActionsBase._check_path` con `@api.constrains('path')`, verbatim:
   literales en línea, mensajes de la fuente con `self.env._`, y el
   `search_count` sobre `ir.actions.actions`.
2. Se retiran el `clean` de `IrActionsBase` y las tres constantes; los
   `clean` de los subtipos siguen llamando a `super().clean()`, que pasa a
   ser el de Django.
3. `IrActionsActWindow._check_model` y `_check_view_mode` con sus
   `@api.constrains`, verbatim, y se retira `IrActionsActWindow.clean`. El
   nombre se comprueba con `not in self.env`, como la fuente:
   `Environment.__contains__` (`src/orm/environments.py:1010-1017`) delega en
   `__getitem__`, que ya acepta el `_name` punteado y la etiqueta de Django
   (`:979-1009`), las dos formas que el `clean` admitía.
4. `TestCheckPath` crea por el ORM y añade el caso que sólo la unicidad
   entre tablas detecta: la misma ruta en una acción de ventana y en una de
   servidor.

## Fuera de esta unidad

`_path_unique` como objeto de tabla (`models.Constraint`) es la tarea de
objetos de tabla en `Meta`; aquí se conserva el `unique=True` del campo.
`_check_children` y `_check_python_code` de la acción de servidor siguen en
su `save`: son la unidad siguiente.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrActionsBase._check_path` con `@api.constrains('path')`; se retiran `IrActionsBase.clean`, `PATH_PATTERN`, `RESERVED_PATH_PREFIXES` y `RESERVED_PATH_WORD` | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:81-103` |
| `IrActionsActWindow._check_model` con `@api.constrains('res_model', 'binding_model_id')`; se retira `IrActionsActWindow.clean` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:270-276` |
| `IrActionsActWindow._check_view_mode` con `@api.constrains('view_mode')` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:300-307` |
| `ClassCheckShadow`, `ClassCheckShadow.__init__`, `ClassCheckShadow.__set_name__` y `ClassCheckShadow.__get__` | `src/orm/models.py` | — (mecanismo del stack: Django declara `Model._check_model` como `classmethod`, `django/db/models/base.py:1746`); prueba: `test_the_django_class_check_keeps_its_own_check_model` |

Prueba: `tests/integration/base/test_ir_actions_constraints.py`, las clases
`TestCheckPath`, `TestCheckModel` y `TestCheckViewMode` reescritas para crear
y escribir por el ORM, más el caso de unicidad entre tablas, el de escritura,
el de un modo que es un espacio y el del *check* de clase de Django. RED
antes del cambio: 13 fallidos de 19.

Anulación (sobre una copia, restaurada y comparada con `cmp`):

- sin el `search_count` y con la regla de espacios del puerto anterior
  (`any(' ' in mode ...)`) caen exactamente los dos casos que dependen de
  ellos: la unicidad entre tablas y `'list, form'` admitido;
- sin `ClassCheckShadow` cae sólo el caso del *check* de clase, con el
  `TypeError` de `django/db/models/base.py:1746`.

- **Cada tabla de acción tiene su propio índice único sobre `path`**
  (medido en `pg_indexes`: `ir_actions_path_key` y uno por cada una de las
  cinco tablas hijas). Ninguno ve una ruta repetida en otra tabla; sólo el
  `search_count` sobre `ir.actions.actions`, que lee `ir_actions` con sus
  hijas, cubre la familia.
- **`_check_model` choca con Django.** `Model.check` llama a
  `cls._check_model()`; con el método de registro de la fuente en su lugar
  el sistema de checks muere y con él todo comando de `manage.py` (lo
  destaparon las dos pruebas de `test_ir_cron_runner.py`, que arrancan
  `cron` en un subproceso). `ClassCheckShadow` conserva el nombre de la
  fuente: sobre un registro es la restricción y sobre la clase es el
  `classmethod` de Django. Búsqueda previa: `src/orm` no tenía descriptor
  para este caso (los dos `__get__` existentes son `IdFromIds` y el mapa de
  `_inherits`).
- **Rojo heredado, no de esta unidad:**
  `tests/unit/orm/test_default_get.py::TestRecNameResolution::test_a_model_with_name_resolves_to_name`
  falla en el subconjunto derivado con `-n 4` también sobre `adcd506c`
  (worktree en HEAD: `1 failed, 1265 passed`) y pasa suelto. Depende del
  orden de ejecución; F2 sobre `73966e6a` lo dio verde.
