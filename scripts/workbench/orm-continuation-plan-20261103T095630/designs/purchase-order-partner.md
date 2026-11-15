# purchase.order.partner_id: el proveedor es un contacto

Unidad: `purchase-order-partner-0397` (TASK-API-0397).

## Contrato medido en la referencia

| Símbolo | Fuente | Aquí antes | Aquí después |
|---|---|---|---|
| `purchase.order.partner_id` | `purchase_order.py:91-94`, `Many2one('res.partner', required=True, index=True)` | FK a `AUTH_USER_MODEL`, opcional | FK a `base.ResPartner`, indexada; `null=True` mientras haya filas sin proveedor |
| `purchase.order.line.partner_id` | `purchase_order_line.py:84`, `related='order_id.partner_id', store=True, index='btree_not_null'` | ausente | `Many2one('base.ResPartner', related=…, store=True)` |

La divergencia la declaraba el propio modelo (*«proveedor (res.partner). Aquí
AUTH_USER»*) y bloqueaba en `purchase_stock` `last_purchase_date` y
`purchase_line_ids` (`purchase_stock/models/product.py:83`,
`res_partner.py:49-70`). Esos dos son sucesores de esta unidad, no parte de
ella.

## Migración de datos

La columna guarda hoy ids de `res.users`; cada usuario tiene su contacto
(`res_users.partner_id`). Tres pasos, para que ninguna restricción de FK vea
un id del otro modelo:

1. `AlterField` a entero sin FK (retira la restricción hacia usuarios);
2. `UPDATE purchase_order SET partner_id = res_users.partner_id`;
3. `AlterField` a FK hacia `res_partner`.

## Casos (RED)

1. `partner_id` de la orden apunta a `res.partner`;
2. la línea tiene `partner_id` almacenado y relacionado con el de la orden;
3. crear una línea copia el proveedor de su orden;
4. cambiar el proveedor de la orden lo propaga a sus líneas.

## Anulación

- quitar el `related` de la línea: caen los casos 3 y 4.

## Diagnóstico: un FK calculado y almacenado sobre BaseModel se escribía nulo

El caso 3 falló con la columna en `NULL` aunque el cómputo del `related`
produjo el contacto correcto. La causa es de la raíz del ORM, no de
`purchase`:

1. el cómputo asigna con `record[name] = valor`; sobre una fila en
   cómputo `BaseModel.__setitem__` lo manda a `field.write`, que llena la
   caché y la marca sucia, pero no toca `__dict__[attname]` de la fila;
2. `_cache_computed_values` (`orm/fields.py`), para un `ForeignKey` sobre
   un recordset nativo, relee el valor del `attname` de la fila
   (`_value_left_by_compute`), porque supone que el cómputo lo asignó por el
   descriptor de Django;
3. el `attname` no está en `__dict__`: la relectura cae en
   `DeferredAttribute.__get__`, carga de la base el `NULL` previo y lo
   vuelve a escribir en la caché, marcado sucio. El vaciado guarda `NULL`.

Medido: con el mismo objeto fila, `record['partner_id'] = v` deja
`__dict__['partner_id_id']` ausente y la lectura por la caché devuelve `v`;
la asignación protegida directa sí se vacía bien (881). Ninguna prueba
existente cubría un `related` almacenado sobre `BaseModel` de punta a punta.

Arreglo, en el punto donde nace: el cubo protegido de
`BaseModel.__setitem__`, después de `field.write`, sincroniza el `attname`
de esas mismas filas cuando el campo es un `ForeignKey`. Las dos formas de
asignar en un cómputo —por el descriptor y por clave— dejan entonces el
mismo valor donde `_cache_computed_values` lo lee.

Anulación del arreglo: retirar la sincronización hace caer los casos 3 y 4.

## Segundo eslabón y medición

La sincronización del `attname` arregló la columna, pero un registro recién
creado seguía leyendo `None`: `_install_field_descriptor`
(`orm/fields.py`) excluía los `related` de `StoredMany2oneIdDescriptor`, el
descriptor que lee el id desde la caché. Un `related` almacenado se quedaba
con el de Django, que lee `__dict__` o la base. Ahora entra como cualquier
FK almacenado.

- 5 de 5 casos (el quinto mide la columna tras vaciar).
- Anular la sincronización del `attname`: cae exactamente el caso de la
  columna.
- Restaurar la exclusión de `related`: caen exactamente los dos casos de
  lectura (3 y 4).
- `tests/unit/orm` más los consumidores de compra: 3250 en verde; los rojos
  eran el guardián de columnas calculadas nuevas (la migración usaba
  `RunSQL` en vez de `ComputeStoredFields`) y dos módulos de prueba que
  creaban el proveedor como usuario. Corregidos los tres.
