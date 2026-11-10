# One2many calculado y almacenado (`compute=` + `store=True`)

Referencia: odoo-tools `abe4040ec1`, Odoo 19 Community.

## Contrato de la referencia

- `Field.__set__` (`odoo/orm/fields.py:1807-1843`): un registro en cómputo
  (protegido) recibe `self.write(records, value)` sin lógica de negocio; uno
  real recibe `records.write({name: convert_to_write(value)})`.
- `_RelationalMulti.write` → `One2many.write_real`
  (`odoo/orm/fields_relational.py:969-1076`): los comandos se aplican en la
  base sobre el `Many2one` inverso (el hijo creado lleva la FK del padre).
- `Field.__get__` (`fields.py:1664-1666`): un campo almacenado pendiente se
  recalcula (`recompute`) antes de leerse; si no, se lee de la base.
- `@api.depends` registra el campo en `field_triggers`, así que escribir una
  dependencia lo marca pendiente (`modified`).

30 declaraciones `One2many(..., compute=..., store=True)` en odoo19c fuera
de pruebas (medido por AST: `sale_order_line.py:107`, `account_tax.py:175`,
`loyalty_program.py:54`, …); 0 en este árbol.

## Estado aquí

- `One2many._get_computed` / `_set_computed` (`orm/fields_relational.py`)
  tratan todo `One2many` calculado como **no almacenado**: el valor vive en
  el `__dict__` de la fila; durante el cómputo se guarda la lista de comandos
  **sin aplicarla**; al asignar fuera del cómputo, `Command.CREATE` crea el
  hijo **sin la FK** del padre.
- Los tres colectores del registro —`field_depends`, `field_computed` y los
  disparadores (`orm/registry.py`)— recorren `model._meta.get_fields()`, que
  no contiene el `One2many` declarado (no tiene columna; la ceguera de
  H-API-1025). Medido con `test_orm.compute.inverse`: tras
  `write({'foo': …})`, `bar` queda pendiente y `child_ids` no; su valor
  cacheado no se invalida nunca.

## Recuperación del primer intento

El primer guion de cambios murió con `AssertionError: 4`: esperaba tres
recorridos `model._meta.get_fields()` en `orm/registry.py` y hay cuatro.
Había aplicado ya `self.model = cls` en `One2many.contribute_to_class`; nada
más. La segunda pasada (por número de línea) cambió tres recorridos y añadió
asignaciones sueltas en `orm/fields.py`. Ese diseño se revisó y se
sustituyó por el de abajo; el diff final se reconstruye desde `323e4c2c`.

## Los cuatro recorridos de `orm/registry.py`

| # | Recorrido | Qué necesita | Fuente canónica | Sin columna | Consumidores |
|---|---|---|---|---|---|
| 1 | `_DerivedCollector._build` (`field_depends`, `field_depends_context`) | todo campo con `@depends`/`related`/`compute` | `model._fields` de la fuente | sí | `resolve_depends`, `get_depends`, disparadores |
| 2 | `_ComputedGrouper._build` (`field_computed`) | todo campo con `compute`, agrupado por método y modelo | ídem | sí | `compute_value`, `recompute`, `protecting` |
| 3 | `_TriggerRegistry._build_inverses` (`field_inverses`) | pares FK ↔ inverso | ídem | ya lo cubre: anota el `One2many` declarado con `setup_inverses` | `modified`, `_update_inverse` |
| 4 | `_TriggerRegistry._build_triggers` | todo campo con dependencias resueltas | ídem | sí | `modified`, `get_field_trigger_tree` |

Medido sobre todos los modelos: `_meta.get_fields()` está contenido entero en
`model_field_registry` (el cuerpo de `_fields`, el registro que el árbol ya
tiene). El registro añade 333 objetos de campo **ajenos** (los del padre que
un hijo por `_inherits` expone) y 18 **propios** sin columna, todos
`fields.One2many`: 11 almacenados sin cómputo, 4 sin almacenar, 2 calculados
sin almacenar y 1 calculado almacenado.

`_collector_fields(model)` = `_meta.get_fields()` (contrato de Django,
relaciones inversas incluidas) + lo propio del registro que `_meta` no ve
(`field.model is model`), por identidad. Sin filtro por tipo: cubre los
calculados almacenados y los no almacenados, y los demás entran sin efecto
(sin dependencias ni cómputo). Lo ajeno se recorre bajo su dueño; tomarlo
bajo el hijo agruparía el cómputo del padre en el hijo. El recorrido 3 no se
toca.

## El protocolo de `Field` en `One2many`

En la fuente `One2many` hereda de `Field` (`fields_relational.py:843`) y con
él `resolve_depends`, el protocolo de caché (`_get_cache`,
`_invalidate_cache`, `_get_all_cache_ids`, `_update_cache`…),
`recompute` y `compute_value` (`fields.py:807-865`, `:1525-1930`). Aquí esos
cuerpos viven en `orm/fields.py` y se instalan sobre `models.Field`, porque
la clase de campo es la de Django. `One2many` no es un `models.Field`, y
`fields_relational` no puede importar `orm.fields` (que lo importa a él).
Decisión: el bucle que ya instala el protocolo en `models.Field` lo instala
también en `One2many` — un único protocolo, un único sitio, sin copia en la
clase. Los atributos que son contrato de la clase sí viven en ella:
`recursive` y `precompute` como parámetros del constructor
(`fields.py:284`, `:287`, por defecto `False`; `resolve_depends` puede
encender `recursive` y apagar `precompute`) y `column_type = None`.

## Lectura y escritura

| Caso | Lectura | Escritura |
|---|---|---|
| `store=True`, fila real | pendiente → `recompute`; si no, la base (`_read_one2many`) | comandos en la base sobre el `Many2one` inverso (≙ `write_real`); un recordset es `SET`; fuera del cómputo, después el `inverse` |
| `store=False` | la caché de la transacción por id (`field_data`); si falta, `compute_value` | en cómputo (protegido): el valor resuelto a la caché; fuera: sobre el valor actual y después el `inverse` |
| fila sin id | el valor en la propia fila | ídem |

Por vivir en `field_data`, el no almacenado lo invalida `modified`
(`_invalidate_cache`) y lo vacía `invalidate_all`.

## Cobertura de la referencia

| Prueba de la referencia | Aquí | Estado |
|---|---|---|
| `test_15_constraint_inverse` (`test_fields.py:822-843`) | `test_15_constraint_inverse` | verde |
| `test_inverse`, bloque de `compute.inverse` (`:649-675`) | `test_compute_inverse_logs` | verde |
| `test_inverse`, `assertQueries` (`:676-679`) | `test_inverse_multiple_compute_inverse_queries` | PENDIENTE, `xfail(strict)` por TASK-API-0510 |
| `test_compute_inverse` (`:4826-4854`) | `test_compute_inverse` (SQL) y `test_compute_inverse_values_without_query_shape` (valores) | SQL PENDIENTE (TASK-API-0510); valores verdes |
| `test_x2many_computed_inverse` (`:4856-4868`) | `test_x2many_computed_inverse` | verde |

`env['x']` devuelve aquí la clase (divergencia de `Environment.__getitem__`);
el recordset vacío de la fuente es `env['x'].browse(())`, convención del
árbol (8 usos). `with_context` sobre él es el de la fuente: la divergencia
está en `__getitem__`, en el alcance de H-API-1083 (tarea #365).

Pruebas propias: materialización (ids enteros, FK del padre, nada de
comandos en la fila), reconstrucción tras vaciar la caché sin recalcular,
lote de dos registros, retroceso con el savepoint, despacho del `inverse`,
invalidación del no almacenado al crear una línea.

## Controles de anulación

| Retirado | Caen |
|---|---|
| campos propios fuera de `_meta` en `_collector_fields` | recompute, cache clear, lote, savepoint, no almacenado |
| `resolve_depends` en `One2many` | los mismos cinco |
| el protocolo de caché en `One2many` | ocho (todo lo que lee el campo) |
| `write_real` en la rama almacenada | siete (todo lo que persiste) |
| el `inverse` en la rama almacenada | `x2many_computed_inverse`, `inverse_dispatch` |
| `recompute` en la lectura | recompute, cache clear, lote, savepoint |

## La familia de escritura (obligaciones `absent` de TASK-API-0485)

El inventario (`outputs/obligation_classification.tsv`) lista 21 símbolos
`absent` en `fields_relational.py`; cuatro son la escritura de este flujo y se
portan con la firma de la fuente:

| Símbolo de la fuente | Aquí |
|---|---|
| `_RelationalMulti.write` (`:737-740`) | `One2many.write`: descarta el recálculo pendiente y escribe por lote |
| `_RelationalMulti.write_batch` (`:742-764`) | `One2many.write_batch`: normaliza tupla, recordset, `False` y lista de ids; despacha a real o nuevo; rechaza la mezcla |
| `One2many.write_real` (`:969-1076`) | `One2many.write_real`, sobre `apply_one2many_commands`, que ya era su cuerpo por registro |
| `One2many.write_new` (`:1078-1121`) | `One2many.write_new`, sobre `write_new_one2many` |

`_write_new_one2many` vivía en `orm/models.py`; se muda a
`fields_relational.py`, donde la fuente declara `write_new`, con nombre
público (`models.py` lo importa, como el descriptor del reverso). Con un
campo calculado `write_new` deja además el valor en la caché del campo: la
de la relación inversa es compartida por todos los `One2many` sobre el mismo
`Many2one`.

La rama almacenada de `_set_computed` escribe con `self.write`, no con un
ayudante propio.

Quedan `absent` de la misma familia, con su dependencia: `_Relational`,
`_RelationalMulti` como clases, `convert_to_record_multi` (tres), el
`write_batch` de `Many2many` y su `write_real`/`write_new`,
`update_db_foreign_key(s)`, y los atributos de `_Relational`
(`check_company`, `context`, `domain`, `relational`). Los de `Many2many`
siguen el mismo patrón y van en la siguiente unidad.

| Retirado | Caen |
|---|---|
| `remove_to_compute` en `write` | `field_write_persists_and_discards_the_pending_compute` |
| la forma tupla en `write_batch` | `normalises_each_value_shape[tuple]` |
| la forma `False` | `normalises_each_value_shape[false]` |
| el despacho a `write_new` | `write_new_keeps_new_lines_in_cache_only`, `refuses_a_mix…` |
| la caché del campo en `write_new` | `write_new_keeps_new_lines_in_cache_only` |

## Gate

Suite completa en el worktree (`gate-o2m2-20261110T073443.log`):
12 568 passed, 66 skipped, 6 xfailed, 2 failed, 5 errors. Atribución, igual
que en el gate de U5: los 5 errores de `test_multidb_isolation.py` exigen base
desechable (`make ci-multidb` se ejecuta aparte); los 2 fallos de
`test_check_workbench.py` son del emplazamiento del worktree (busca thyrox como
hermano del repo; 20/20 en el árbol principal). Los 6 xfail son los 4 previos
y las 2 aserciones de SQL pendientes de TASK-API-0510.

Tras el gate se partieron líneas largas que la admisión rechazaba (siete de
ellas ya existían y cambiaron de posición). `registry.py` y la prueba quedan
con AST idéntico al del gate; `fields_relational.py`, idéntico sin contar el
texto de los docstrings. El subconjunto da 38 passed, 2 xfailed sobre la
versión commiteada.
