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

## 5. Medición y causas (2026-11-17)

La hipótesis inicial —`modified` no marca el recálculo al cambiar
`product_qty`— era **falsa**. Medido con sondas, sin suponer:

1. **El valor inicial ya fallaba** (`price_unit` `False` antes de cambiar
   nada). El cómputo sí corría y saltaba la línea: `company_id` era
   `None`. La fuente declara `company_id` `related='order_id.company_id',
   store=True` (`odoo19c: addons/purchase/models/purchase_order_line.py:53`);
   el porte lo tenía como columna sincronizada en `save()` con la razón
   «este ORM no dispara el `related=` con columna», que **ya era falsa**: el
   mismo modelo declara `partner_id` `related=..., store=True` (línea 100).
   Corrección: la declaración de la fuente, sin `ondelete` → `set null`
   (`odoo19c: odoo/orm/fields_relational.py:274-282`); cierra además la fila
   `purchase.PurchaseOrderLine.company_id` del contrato de borrado.
2. **El cambio de cantidad no cambiaba de vendedor.** `price_unit` sí entra
   en `tocompute`; `selected_seller_id` no se invalidaba porque
   `_compute_selected_seller_id` no tenía `@api.depends`. La fuente declara
   `('product_id', 'product_id.seller_ids', 'partner_id', 'product_qty',
   'order_id.date_order', 'product_uom_id')` (`:265`).
3. **La línea guardada perdía el precio** al retirar la sincronización: el
   precio sólo se calculaba por el `modified(company_id)` que esa
   sincronización disparaba. `create` protege el grupo de un calculado
   editable presente en `vals` (`odoo19c: odoo/orm/models.py:4681-4684`);
   `name` (`default=''`) y `discount` (`default=0`) traían un defecto que la
   fuente no declara, y protegían `price_unit`. Corrección: sin esos
   defectos; `discount` admite `NULL` como el `Float` no obligatorio.
4. **Un `discount` ausente llegaba como `None` a la aritmética.** La fuente
   lo lee como cero (`Float`/`Monetary.convert_to_record`, `odoo19c:
   odoo/orm/fields_numeric.py:171-172,282-283`); `FloatField` y
   `DecimalField` caían en el conversor genérico. Corrección: los dos
   `convert_to_record`, con el mismo mecanismo que el `Integer`.

## 6. Mecanismos probados y retirados

Dos cambios al ORM se escribieron durante la medición y **se retiraron**
porque su anulación no cambia ningún resultado:
- saltar el `__dict__` para un almacenado calculado con id `NewId`;
- la rama de cómputo y el `recompute` previo en `StoredMany2oneIdDescriptor`.

No resolvían una causa medida: el `company_id` resuelve por otra ruta.

## 7. Anulaciones (cada una cae sólo en lo suyo)

| Anulación | Cae |
|---|---|
| A: sin la rama `NewId` en el id de FK | nada (22 passed) → retirado |
| B: sin `recompute` previo en el id de FK | nada (22 passed) → retirado |
| C: sin `_decimal_convert_to_record` | el resincronizado de empresa y los 2 casos `Decimal` |
| D: sin `@api.depends` del vendedor | subir, bajar la cantidad y la línea guardada (3) |
| E: con los defectos `name`/`discount` | la línea guardada (1) |
| F: sin `related` en `company_id` | los 5 casos de `new()` y los 2 de empresa de la línea (7) |

Las conversiones portadas son `_float_convert_to_record` y
`_decimal_convert_to_record` (`odoo19c: odoo/orm/fields_numeric.py:171-172`),
con su prueba directa en `tests/unit/orm/test_numeric_convert_to_record.py`;
la conducta de la línea, en
`tests/unit/purchase/test_purchase_new_line_recompute.py`.

Sucesor: `Float`/`Monetary.convert_to_cache` con el redondeo por dígitos y
por moneda (`odoo19c: odoo/orm/fields_numeric.py:165-169,266-280`), unidad
`orm-float-monetary-convert-to-cache-0485`.

## 8. F2 sobre `32a654c8`: la regla de empresa leía el `related` sin volcar

F2 se detuvo en el primer fallo (`--maxfail=1`, 7 min en vez de 22):
`test_the_purchase_user_confirms_under_the_threshold`. La misma prueba pasa
en `89921ece` sobre la misma base; bisección por anulación: la causa es
retirar `_sync_company`.

Dos defectos, los dos ocultos por la sincronización:

1. **La prueba leía datos de preparación fuera de `sudo`.**
   `order.company_id` como el usuario por omisión de la prueba sólo pasaba
   porque `_sync_company` había dejado el valor en caché dentro de `sudo`.
   En la fuente el registro sale de un entorno `su` y lo conserva; aquí el
   entorno es el ambiente. Corrección: leerla en `sudo`, como el resto de la
   preparación. El contrato que la prueba mide no cambia.
2. **La regla de empresa veía `company_id` en `NULL`.** Tras `create`, el
   `related` almacenado queda pendiente en `tocompute` (medido: columna
   `NULL`; tras `flush_all`, el id de la empresa). La fuente evalúa las
   reglas en memoria con `filtered_domain`
   (`odoo19c: odoo/orm/models.py:4131-4149`), y leer procesa el recálculo;
   aquí `AccessQuerySet._check_access` evalúa en SQL sin volcar. Corrección:
   `self.flush_model()` antes de `Rule._get_failing`, el equivalente de
   `execute_query` → `flush_query` (`odoo19c: odoo/orm/environments.py:515-535`).
   Anulado, cae exactamente ese caso.

## 9. F2 sobre `940f00c6`: `or` sobre `Decimal` perdía la escala

`test_sale_order_sms_confirmation_send`: el SMS decía `total $0` donde
esperaba `$0.00`. `value or Decimal(0)` cambia `Decimal('0.00')` —un cero
presente, falso en Python— por `Decimal(0)`. El `or` de la fuente opera
sobre `float`, que no tiene escala. Corrección: sólo la ausencia
(`None`/`False`) se lee como cero. Prueba
`test_a_present_decimal_zero_keeps_its_scale`; anulado, caen exactamente
ese caso y el SMS.

## 10. F2 sobre `805fcdf7`: la columna que pasa a calculada se calcula

`test_every_added_computed_column_is_computed` (guardián de TASK-API-0516)
pide un `ComputeStoredFields` para `purchaseorderline.company_id`, que ahora
es `related` con columna. Va en una migración nueva (`0025`), no en `0023`:
`0023` ya está aplicada en las bases de prueba y no volvería a correr.
