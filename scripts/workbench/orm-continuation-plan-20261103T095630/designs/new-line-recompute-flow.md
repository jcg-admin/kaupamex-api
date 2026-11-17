# Línea de compra en `new()`: recalcular precio y fecha al cambiar la cantidad

Unidad `orm-new-record-stored-compute-0485` (TASK-API-0485). Referencia:
`odoo-tools` en `abe4040ec1`. Orden: referencia → stack → Consumer →
TASK → implementación (instrucción 4.3.2 §3).

## 1. Referencia (medida, comando: `sed -n` sobre las líneas citadas)

| Elemento | Evidencia |
|---|---|
| Creación | `BaseModel.new`, `odoo19c: odoo/orm/models.py:6441-6461`: `browse((NewId(origin, ref),))` y `_update_cache(values, validate=False)`; no hay `modified` en la inicialización |
| Identidad | el `NewId` es el id del registro; la caché del campo se indexa por él |
| Asignación | `Field.__set__`, `odoo19c: odoo/orm/fields.py:1807-1847`: un id falso va al cubo nuevo → `protecting(field_computed[campo])`, `write`, `modified([nombre])` (y `modified(before=True)` sólo si es relacional) |
| Notificación | `BaseModel.modified`, `odoo19c: odoo/orm/models.py:6756-6838`: después del cambio `tomark = transaction.tocompute`; un calculado almacenado del árbol de disparo recibe los ids (`:6827-6828`), uno sin columna se invalida (`:6829-6832`) |
| Dependencias | `_compute_price_unit_and_date_planned_and_name`, `odoo19c: addons/purchase/models/purchase_order_line.py:404`: `@api.depends('product_qty', 'product_uom_id', 'company_id', 'order_id.partner_id')`; `product_qty` está en la raíz del árbol |
| Recálculo | `Field.__get__`, `odoo19c: odoo/orm/fields.py:1662-1663`: un calculado almacenado llama a `self.recompute(record)` antes de leer la caché; `Field.recompute` (`:1850`) → `compute_value` (`:1897`) |
| Lectura | acierto de caché (`:1665-1673`) |
| Persistencia | ninguna mientras sea nuevo |
| Control negativo | un campo fuera de `@api.depends` (p. ej. `name`) no marca el cálculo |

`price_unit` y `date_planned` salen del **mismo** método: un recálculo
los escribe a los dos (`purchase_order_line.py:404-475`).

## 2. Stack

Django no tiene notificación de dependencias: una asignación escribe
`instance.__dict__`. El enganche es el descriptor
(`orm.fields.FieldDescriptor`), que este árbol ya instala.

## 3. Consumer (leído, sin ejecutar)

- `FieldDescriptor.__set__` (`src/orm/fields.py:1925-2087`) porta los tres
  cubos; el de fila nueva (`:2050-2075`) protege, escribe y llama a
  `modified`, como la fuente.
- `modified` (`src/orm/models.py:5061-5147`) y `_modified_triggers`
  (`:4991-5033`) siguen la fuente; `record_ids` acepta el `NewId`.
- `FieldDescriptor.__get__` llama a `field.recompute(instance)`
  (`src/orm/fields.py:1700`); `recompute` (`:5272`) filtra por
  `tocompute`.

La lectura no localiza la diferencia: las tres mitades están portadas.
La causa se mide con la prueba discriminante, no se supone.

## 4. Pruebas

`tests/unit/purchase/test_purchase_new_line_recompute.py`: valor inicial,
subida de cantidad, bajada, control negativo (`name`), control de
compatibilidad con la fila guardada.

## 5. Medición y causa

Pendiente: se ejecuta cuando F2 libera las bases.
