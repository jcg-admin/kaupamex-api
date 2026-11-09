# TASK-API-0510 — `_write`, `_write_multi` y el volcado de `_flush`

Fecha: 2026-11-09T23:15:10Z. Referencia: odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`, `odoo19c: odoo/orm/models.py`.

## Contrato de la referencia

- `_write(self, vals)` (`:4520-4522`): `self._write_multi([vals] * len(self))`.
- `_write_multi(self, vals_list)` (`:4524-4608`):
  1. `assert len(self) == len(vals_list)`; vacío → retorna;
  2. `parent_records = self._parent_store_update_prepare(vals_list)`;
  3. con `_log_access`: `log_vals = {'write_uid': uid, 'write_date': now}`
     y `vals_list = [log_vals | vals ...]` — el volcado de un campo
     calculado también fecha la fila;
  4. agrupa por conjunto de campos y emite `UPDATE … FROM (VALUES …)` por
     lotes de `UPDATE_BATCH_SIZE`; ramas de `translate` y
     `company_dependent` en la expresión;
  5. `if parent_records: parent_records._parent_store_update()`.
- `_flush` (`:6386-6432`): saca del cache los ids sucios por campo, los
  ordena por máscara de campos sucios, y por lotes de 1000 construye un
  `vals_list` (`f.get_column_update(record)`) y llama
  `model.browse(some_ids)._write_multi(vals_list)`.
- Consumidores medidos: `_write_multi` sólo lo llama `_flush` (`:6432`);
  `_write` no tiene llamador en `odoo/` ni en `addons/` (fuera de tests).

## Estado de este árbol

`_flush` (`src/orm/models.py`, función de módulo) recorre los ids y, por
fila, asigna el valor del cache y llama `row.save(update_fields=names)`;
los M2M van a `_flush_m2m`. No existe `_write` ni `_write_multi`, no se
prepara ni actualiza `parent_path`, y el volcado **no fecha la fila**
(`updated_at` no entra en `update_fields`), a diferencia de `write`
(`:2973`), que sí la nombra.

## Por qué el `UPDATE … FROM VALUES` no sustituye a `save()` todavía

Medido el 2026-11-09:

- **8 modelos** con campos calculados almacenados sobrescriben `save()`, y
  la sobrescritura **calcula**: `SaleOrderLine.save` → `_compute_amount` y
  `order._compute_amounts()`; `AccountMoveLine.save` → `_compute_balance`,
  `journal_id`/`company_id`; `AccountAccount`, `AccountPaymentMethodLine`,
  `CrmLead`, `SaleOrder`, `ResPartner`, `BaseAutomation`. Es el trabajo que
  la referencia hace en el grafo de `@api.depends`.
- **Receptores** `pre_save`/`post_save` sobre modelos volcados: dos
  globales (`orm.models.run_precompute`, `base_automation`), y por
  remitente `l10n_mx` (`account.move.line`, `account.tax`,
  `account.account`), `account_fleet`, `helpdesk`, `account`, `stock`,
  `payment`, entre otros (`grep -nE "(pre_save|post_save)\.connect|@receiver"`).
- La automatización sobre recómputo: la referencia la dispara parcheando
  `_compute_field_value` (`base_automation.py:909-946`); aquí ese gancho
  está declarado bloqueado (`addons/base_automation/models/base_automation.py:51`)
  y el único camino por el que hoy llega un recómputo a
  `_dispatch_create_write` es el `post_save` del volcado.

Un `UPDATE` crudo saltaría las tres cosas. No es un detalle de
rendimiento: rompería la cascada de importes y las automatizaciones.

## Decisión — una sola implementación, con divergencia de enunciado declarada

1. `BaseModel._write_multi(self, vals_list)` con la estructura de la
   referencia: aserción de longitud, retorno en vacío,
   `_parent_store_update_prepare`, `_log_access` (`updated_at`, la columna
   de este árbol para `write_date`; `write_uid` no existe aquí, ver
   `LOG_ACCESS_COLUMNS` en `orm/model_classes.py:1054`), escritura y
   `_parent_store_update()` al final.
2. **Divergencia de enunciado:** la escritura por fila es
   `save(update_fields=...)` y los M2M van a `_flush_m2m`, no un
   `UPDATE … FROM VALUES` por lotes. Justificación contractual: el
   `save()` y sus señales alojan cómputos y automatizaciones que la
   referencia aloja en el grafo de dependencias. No hay un segundo camino
   activo: `_flush` y `_write` pasan **los dos** por `_write_multi`.
3. `BaseModel._write(self, vals)` = `_write_multi([vals] * len(self))`.
4. `_flush` construye el `vals_list` por id, ordenado por máscara de campos
   sucios y por lotes de 1000 como la referencia, y llama
   `model.browse(ids)._write_multi(vals_list)`.
5. Las ramas `translate` y `company_dependent` de la expresión SQL no
   aplican al enunciado `save()`: `translate=True` aún no traduce
   (`fields_textual.py:204`) y `company_dependent` escribe por su
   descriptor. Quedan declaradas, no omitidas.

Sucesor del enunciado por lotes: cuando los cómputos alojados en `save()`
de los 8 modelos pasen a `@api.depends` y la automatización sobre recómputo
tenga su gancho, el `UPDATE … FROM VALUES` puede reemplazar el `save()`.
Condición de cierre medible: `post_save.has_listeners` sin receptores de
cómputo y cero sobrescrituras de `save()` con cálculo en modelos con campos
calculados almacenados. Registrado como DESCONOCIDO con esa condición; no
se abre TASK hasta que la primera de las dos se cumpla.

## Casos (RED)

1. `_write_multi` con longitudes distintas → `AssertionError`.
2. `_write_multi([])` sobre vacío → no consulta, retorna `None`.
3. `_write` aplica el mismo `vals` a cada fila (dos filas, una consulta de
   comprobación por `read`).
4. `_write_multi` con `parent_id` nuevo reescribe el `parent_path` del
   subárbol (vía `_parent_store_update_prepare`/`_parent_store_update`).
5. `_write_multi` fecha la fila: `updated_at` avanza aunque no esté en
   `vals`.
6. `_flush` pasa por `_write_multi`: un espía ve una llamada con los ids
   sucios y un `vals_list` con el valor calculado.
7. El volcado de un campo calculado fecha la fila (`updated_at` avanza) —
   rojo hoy.
8. Control: un receptor `post_save` del modelo sigue recibiendo el volcado
   (la divergencia declarada se conserva).

Anulación prevista: hacer que `_flush` escriba sin `_write_multi` tumba 6
y 7; quitar `_log_access` de `_write_multi` tumba 5 y 7; quitar la
preparación del `parent_path` tumba 4; 8 no depende de ninguna y sigue.

## Regresión de impacto

Derivada: archivos de `tests/` que nombran `flush_model`, `flush_recordset`,
`_flush`, `compute=` con `store=True`, o los 8 modelos; más el gate
integral antes de aceptar.

## RED, GREEN y anulación (2026-11-09)

- RED sobre `a922d9c9`: `7 failed, 1 passed`. Pasa sólo el control 8
  (`post_save` recibe el volcado), que no depende del cambio. El 7 cae por
  la razón prevista: el volcado escribe `size1` y `updated_at` sigue en
  2001.
- Sujeto de los casos 6-8: `test_orm.model_child_m2o.size1`
  (`@depends('parent_id.name')`). La primera versión usaba
  `model_parent_m2o.cost` (`@depends('child_ids.cost')`) y la sonda mostró
  que **ese recómputo no llega a la base**: tras `child.write({'cost': 7})`
  y `flush_model()` el padre sigue en 2. No es del volcado ni del árbol de
  disparo (el árbol y el inverso son correctos; `_modified_triggers` cede
  el padre si se le llama). Causa medida: `write` protege los calculados
  que escribe y `FieldDescriptor.__set__` entra en la rama protegida
  (`src/orm/fields.py:1928-1933`) sin anunciar `modified()`; la fuente
  llama `self.modified(vals)` tras escribir (`odoo19c:
  odoo/orm/models.py:4484`). Sucesor: **TASK-API-0511**.
- Segundo defecto, destapado por la misma sonda: **leer** `child.parent_id`
  marca `parent.cost` y `child.size1`/`size2` en `tocompute` sin cambio
  alguno (vacío antes de la lectura, tres marcas después). Esa marca
  espuria es la que hacía pasar las primeras sondas. Causa sin medir;
  sucesor: **TASK-API-0512**. Sonda conservada fuera del árbol
  (`scratchpad/probe-write-computed-modified.py`).
- GREEN: `8 passed`; con `test_parent_store_methods.py`, `14 passed`.
- Anulación, cada una restaurada y verificada con `cmp`:
  (a) `_flush` llama `BaseModel._write_multi` sin pasar por el método →
  cae exactamente el 6; (b) sin la fecha de `_log_access` → caen
  exactamente el 5 y el 7; (c) sin `_parent_store_update_prepare` → cae
  exactamente el 4.
- Lo que este cambio no toca: `write()` (`models.py`, rama de
  `self.save(update_fields=...)`) escribe directo y no por caché + volcado
  como la fuente (`field.write` y después `_flush`). Las dos rutas usan el
  mismo enunciado (`save(update_fields)`) y la misma fecha (`updated_at`),
  así que no divergen en conducta; llevar `write` a caché + volcado es otra
  unidad.

## Regresión de impacto: `_flush` no es sólo de `BaseModel`

Primera regresión derivada (23 directorios): `18 failed, 9373 passed`.
Todas con la misma causa: `AttributeError: type object '<M>' has no
attribute 'browse'` sobre `ResPartner`, `AccountAccount`,
`AccountMoveLine` y tres modelos de prueba. `_flush` es un método de motor
colgado de **todo** `django.db.models.Model` y `QuerySet`
(`src/orm/models.py`, el bucle de `_engine_method`), y esos modelos no
tienen recordset. El diseño de arriba suponía que sólo un `BaseModel`
volcaba: premisa falsa, medida por la regresión.

Corrección, sin dos escritores:

- `_write_rows(model, ids, vals_list)` es la única escritura física: pide
  las filas al `_base_manager` (el gestor físico; el contrato de
  `tests/unit/orm/test_flush_manager_contract.py` exige una sola consulta
  `pk__in` por lote y no tocar el gestor público), no recrea una fila que
  ya no existe, fecha con `_log_access` y guarda con `save(update_fields)`.
- `BaseModel._write_multi` añade la capa de recordset de la fuente
  (aserción, `_parent_store_update_prepare` / `_parent_store_update`) y
  delega en `_write_rows`.
- `_flush` llama `model.browse(ids)._write_multi(vals_list)` si el modelo
  es `BaseModel`; si es un modelo de Django sin recordset, `_write_rows`
  directo: no tiene `parent_path` que preparar por esta vía.

Tras corregir: los seis archivos que cayeron más los de la unidad,
`140 passed`. Anulación repetida sobre la estructura nueva, mismo
resultado exacto que antes (a → 6; b → 5 y 7; c → 4).
