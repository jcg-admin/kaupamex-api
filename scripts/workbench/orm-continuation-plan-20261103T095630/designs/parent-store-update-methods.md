# Unidad siguiente (TASK-API-0485) — `_parent_store_update_prepare` y `_parent_store_update` como métodos de `BaseModel`

Seleccionada tras `d9e3555c`: el inventario estructural
(`orm-symbol-presence-census-20260910T175850/outputs/inventory_by_kind.tsv`,
generado 19:08, desfasado respecto de las unidades de `_read_group`) los
marca `absent` en `src/orm/models.py`. Medido hoy: no existen como métodos;
existen como **funciones de módulo por fila** (`_reparented`,
`_parent_store_update`, `src/orm/models.py:1229-1279`), consumidas por
`BaseModel.write` (`:2976`) y por `ir.ui.menu` (`ir_ui_menu.py:66,393`).

Autoridad: `odoo19c: odoo/orm/models.py:4985-5054` (odoo-tools
`abe4040ec1`).

## Contrato

- `_parent_store_update_prepare(vals_list)`: sin `_parent_store` → vacío;
  agrupa ids por el nuevo padre de cada `vals`; sin cambios de padre →
  vacío; `flush_recordset([_parent_name])`; devuelve, en orden de id, los
  registros cuyo padre **cambia** de verdad (`!= nuevo OR IS NULL`, o
  `IS NOT NULL` si el nuevo es falso).
- `_parent_store_update()`: agrupa `self` por padre; rechaza recursión
  (`UserError("Recursion Detected.")`); reescribe el prefijo de
  `parent_path` de los registros y sus descendientes con un único `UPDATE`
  por grupo; refresca el caché.

## Decisión

Portar los dos como métodos de `BaseModel` sobre el recordset (varios
registros, varios padres), y que las funciones por fila deleguen en ellos,
sin cambiar a sus consumidores. Lo que la función por fila declara como
adaptación (`= ANY(%s)` por la adaptación de tuplas de psycopg 3) se
conserva.

## Casos (`tests/unit/orm/test_parent_store_methods.py`, `test_orm.category`)

1. sin cambio de padre → vacío; con cambio real → esos registros, por id;
2. un `vals` que repite el padre actual no cuenta;
3. `_parent_store_update` sobre dos registros de padres distintos reescribe
   a ambos y a sus descendientes;
4. mover un nodo bajo su propio descendiente → `UserError`.

## RED, GREEN y anulación (2026-11-09)

- RED sobre `d9e3555c`: `4 failed` — `AttributeError` de los dos métodos.
- GREEN: `4 passed` (más las pruebas de `ir.ui.menu`: `7 passed`). El caché
  se actualiza como la fuente: `field._update_cache` por nodo y
  `records.modified(['parent_path'])`.
- Sin la condición de cambio real: cae exactamente 1; sin el rechazo de
  recursión: cae exactamente 1.

Pendiente, declarado: las funciones por fila (`_reparented`,
`_parent_store_update` de módulo) todavía no delegan en los métodos; sus
consumidores (`BaseModel.write`, `ir.ui.menu`) siguen sobre ellas. La
delegación es el paso siguiente de esta unidad, con su propia regresión.

## Reconciliación de las rutas (consumidores ejecutables)

Referencia: `write` → `_write` → `_write_multi` (`odoo19c: models.py:4520-4608`)
llama `_parent_store_update_prepare(vals_list)` **antes** de escribir y
`parent_records._parent_store_update()` **después**. En Kaupamex el
`write` del recordset escribe fila a fila con `RecordLoaderMixin.write`,
que consultaba `_reparented` antes de guardar y `_parent_store_update`
(función) después.

Decisión: el propietario canónico son los métodos de `BaseModel`. Las dos
funciones de módulo delegan en ellos cuando el registro es un `BaseModel`
(el único que `_maintains_parent_store` admite): `_reparented` devuelve si
`_parent_store_update_prepare([{padre: nuevo}])` no es vacío, y
`_parent_store_update` llama al método. El cuerpo por fila de la función
queda sólo para `ir.ui.menu`, que es un modelo de Django sin recordset
(`TimeStampedModel`) y mantiene su `parent_path` en `save()`: no hay
método al que delegar, y esa es la justificación de que convivan.

Pruebas: `write` con cambio de padre pasa por el método (espía: una llamada
con el id del registro) y reescribe al descendiente; `write` que repite el
padre no lo llama. Anulación: sin la delegación de la función cae
exactamente el primero; con `_reparented` siempre verdadero cae exactamente
el segundo. Regresión de los 36 archivos de prueba que nombran
`parent_path`, `child_of` o `_parent_store`: en curso.
