# Cómputos invocados por `save()` sobre campos calculados almacenados

Sucesor de `stored-computes-on-django-create.md` («Corrección de una
afirmación y duplicado medido»). Ocho modelos con calculados almacenados
declarados invocan sus métodos `_compute_*` dentro de `save()`.

## Contrato de la fuente

En Odoo 19 un calculado almacenado se calcula por el motor, nunca por la
sobrescritura de `create`/`write`:

- **creación**: los precompute los calcula `_add_precomputed_values`
  (`odoo19c: odoo/orm/models.py:4814-4846`) antes del INSERT; los demás, el
  `modified(..., create=True)` de `_create` (`:4930-4933`) y el volcado.
- **modificación**: `write` llama `modified(vals)` y el volcado recalcula los
  dependientes; la columna nueva llega en el `UPDATE` del `_flush`.

Las cinco cantidades de `sale.order.line` (`price_subtotal`, `price_tax`,
`price_total`, `price_reduce_taxexcl`, `price_reduce_taxinc`) son
`store=True, precompute=True` (`addons/sale/models/sale_order_line.py:190-209`)
y su `create` (`:1322`) no las toca.

## Lo que hace el árbol, por vía

`SaleOrderLine.save` (`addons/sale/models/sale_order_line.py:700-716`):

1. invoca `_compute_amount` y los dos `_compute_price_reduce_*`;
2. si llega `update_fields`, le añade las cinco columnas
   (`COMPUTED_AMOUNT_FIELDS`), para que un `save(update_fields=['price_unit'])`
   escriba también los importes;
3. `super().save()`; luego `self.order._compute_amounts()`.

| Vía | Cómputos antes del INSERT/UPDATE | Después | Duplicado |
|---|---|---|---|
| alta | `save()` + precompute de `pre_save` | 0 (el alta los protege) | **sí, 2 → debe ser 1** |
| modificación con `update_fields` | `save()` | 0: la escritura del cómputo descarta la marca (`Field.write` → `remove_to_compute`) | no |

La vía de modificación no duplica y tiene consumidores que dependen de que
la columna se escriba en el mismo `save()`: `addons/sale/services.py:249`
(`product_uom_qty`) y `:400` (`price_unit`), y
`addons/stock/models/stock_move.py:2148`. Retirar ahí el cálculo exigiría que
esos consumidores vuelquen antes de leer; no es parte de esta unidad.

## Corrección (por modelo)

**`SaleOrderLine`**: en alta (`self._state.adding`), no invocar los tres
cómputos: el precompute de `pre_save` ya los calcula sobre la misma fila,
después de `_coerce_amount_operands()`. En modificación, sin cambios.

Prueba RED (`tests/unit/sale/test_line_amount_computes_once.py`):

- alta por `objects.create`: `_compute_amount` corre **una** vez en total y
  los cinco importes persistidos son los de la línea;
- modificación con `save(update_fields=['price_unit'])`: la columna
  `price_subtotal` cambia en la base sin volcado previo (consumidor de
  `services.py:400`) y el cómputo corre una vez.

Anulación: restituir la llamada en alta hace caer exactamente el conteo de
alta.

**Los otros siete** (`CrmLead`, `SaleOrder`, `ResPartner`, `AccountAccount`,
`AccountMoveLine`, `AccountPaymentMethodLine`, `BaseAutomation`): mismo
procedimiento, modelo por modelo, con una pregunta previa que esta
investigación no cierra para ninguno: si el cómputo invocado es precompute
(lo calcula `pre_save`) o no (lo calcula el marcado de creación tras el
INSERT). En el segundo caso retirar la llamada en alta deja la columna sin
valor hasta el volcado, y un consumidor que lea la base justo después del
`save()` lo notaría; se mide con la suite derivada de cada modelo antes de
retirarla.

*Métrica:* llamadas al método por vía, con espía sobre la clase.
*Ciega a:* consumidores que lean la columna por SQL crudo sin volcar.

## Revisión con el registro vivo: población real y responsable único (2026-11-12)

### Población medida, no inferida del AST

`probes/eager_save_computes.py` cruza los métodos `_compute_*` que invoca
cada `save()` con los campos que los **declaran** en el registro. El barrido
AST anterior contaba ocho modelos; con el registro son **seis**.
`ResPartner` y `BaseAutomation` invocan métodos que ningún campo declara
como calculado almacenado, así que no duplican nada.

| Modelo | precompute | readonly sin precompute | editable |
|---|---|---|---|
| `account.AccountAccount` | `account_type` | `internal_group` | `tags` |
| `account.AccountMoveLine` | `balance` | — | — |
| `account.AccountPaymentMethodLine` | — | — | `name` |
| `crm.CrmLead` | `team_id` | 11 (`date_last_stage_update`, `date_open`, `day_close`, `day_open`, `email_domain_criterion`, `email_state`, `phone_state`, `prorated_revenue`, `recurring_revenue_monthly`, `recurring_revenue_monthly_prorated`, `recurring_revenue_prorated`, `won_status`) | 11 |
| `sale.SaleOrder` | `validity_date` | — | — |
| `sale.SaleOrderLine` | los 5 importes | — | — |

### Qué duplica y por qué

Contrato de la fuente (odoo-tools `abe4040ec1`, `odoo/orm/models.py`):
`create` (`:4611`) arma `vals` con `_prepare_create_values` →
`_add_precomputed_values` (`:4810`, `:4814-4846`), protege
(`:4681-4684`), llama `_create` (`:4711`), y ésta inserta, puebla la caché y
marca todo lo calculado con `modified(self._fields, create=True)` bajo
`env.protecting` (`:4929-4933`); después corren los inversos bajo la misma
protección (`:4713-4735`) y `_validate_fields` (`:4741`, `:4949`). El valor
de un calculado que no es precompute llega a la columna en el volcado. Nada
se calcula dos veces para el mismo estado de dependencias.

En el árbol, una fila creada por `save()` de estos modelos pasa por:

1. el `save()` del modelo, que invoca los cómputos (fila sin guardar);
2. `pre_save` → `_add_precomputed_values`, que vuelve a calcular **todo
   precompute readonly** (`_precomputable_fields` los incluye siempre);
3. el INSERT;
4. `post_save` → marcado de creación, que protege lo dado y editable, y los
   precompute, y **vuelve a marcar los readonly sin precompute**.

| Clase de campo | Ejecuciones en alta | Debe ser |
|---|---|---|
| precompute | 2 (pasos 1 y 2) | 1 |
| readonly sin precompute | 2 (paso 1 y volcado tras el paso 4) | 1 |
| editable | 1 (la asignación del paso 1 cuenta como dada y queda protegida) | 1 |

### Por qué no basta con retirar las llamadas de `save()`

Para los precompute, sí: el pase de `pre_save` es su responsable en el
núcleo, como `_add_precomputed_values` en la fuente.

Para los readonly sin precompute, no. En la fuente su valor llega en el
volcado y todo lector del ORM vuelca antes de consultar. Aquí un
`QuerySet` de Django no vuelca (medido: ningún gancho de volcado antes de
consultar en `src/orm/`), y el cálculo de `save()` es lo que pone el valor en
el INSERT. Retirarlo dejaría la columna vacía hasta el volcado para todo
lector directo. Lo que sobra no es el cálculo previo al INSERT: es el
**segundo marcado** para el mismo estado de dependencias.

### Corrección en el núcleo, una sola

1. `orm.models.compute_before_insert(instance, *methods)`: invoca cada método
   sobre la fila sin guardar y anota en la fila los campos que esos métodos
   calculan.
2. El pase de precompute de `pre_save` no recalcula un campo ya anotado.
3. El marcado de creación de `post_save` protege, además, los campos
   anotados con su grupo: su valor es el de su cómputo para el estado de
   dependencias con que se insertó la fila. Un cambio posterior de
   dependencias marca de nuevo, como siempre.
4. Los seis `save()` usan, en alta, `compute_before_insert` sólo para los
   cálculos que no son precompute; los precompute se dejan al pase. En
   modificación siguen igual: no duplican (la escritura del cómputo descarta
   la marca) y `sale/services.py:249`, `:400` y `stock/models/stock_move.py:2148`
   dependen de que el mismo `save()` escriba la columna.

### Pruebas (RED antes de la corrección)

- conteo de invocaciones por método en alta por `objects.create` y por
  `save()`: 1 para `SaleOrderLine._compute_amount`,
  `CrmLead._compute_won_status` (readonly), `CrmLead._compute_team_id`
  (precompute), `AccountAccount._compute_internal_group`;
- valores correctos tras el volcado;
- una dependencia posterior recalcula: cambiar `probability` de la
  iniciativa recalcula `won_status`/`prorated_revenue`;
- los controles de `test_create_protection.py` siguen pasando.

Anulación: sin la anotación en el marcado de creación vuelven a 2 los
readonly; sin el salto en el pase de precompute vuelven a 2 los precompute.

## Causa medida y corrección aplicada (sobre `f77418eb`)

### La causa no era sólo el `save()` del modelo: era el volcado

Conteos RED (`tests/unit/orm/test_compute_before_insert.py`, espía sobre la
clase, alta por `objects.create` seguida de `flush_all`):

| Método | Antes | Después |
|---|---|---|
| `SaleOrderLine._compute_amount` (precompute) | 2 | 1 |
| `CrmLead._compute_won_status` (readonly) | **12** | 1 |
| `CrmLead._compute_team_id` (precompute) | **12** | 1 |
| `AccountAccount._compute_internal_group` (readonly) | 3 | 1 |
| `AccountAccount._compute_account_type` (precompute dado) | 2 | 0 (dado: la fuente no lo calcula) |
| `AccountMoveLine._compute_balance` (precompute editable) | 1 | 1 |
| `SaleOrder._compute_validity_date` (precompute) | 1 | 1 |

Retirar el cálculo de `CrmLead.save` en alta bajó el conteo de 12 a **11**,
no a 1. La traza de las diez restantes salía de `flush_all → flush_model →
_flush → _write_rows`, y `_write_rows` guardaba cada fila con
`row.save(update_fields=...)`: **cada volcado ejecutaba la sobrescritura de
`save()` del modelo**. En `CrmLead`, esa sobrescritura en modificación corre
los 24 cómputos, sus asignaciones vuelven a ensuciar campos, y el volcado da
otra vuelta: diez vueltas.

En la fuente, `_flush` escribe por `_write`/`_write_multi`
(`odoo19c: odoo/orm/models.py:4520-4526`, *"Low-level implementation of
write()"*): SQL más `write_date`/`write_uid`, sin la lógica de negocio que
vive en `write`. `designs/write-multi-flush.md` había declarado ese
`save(update_fields)` como divergencia porque «el `save()` y sus señales
alojan cómputos y automatizaciones que la referencia aloja en el grafo de
dependencias». El grafo ya existe y aloja esos cómputos: la justificación
caducó y la divergencia producía exactamente la cascada.

### Corrección en el núcleo

`_persist_columns(row, names)` (`src/orm/models.py`): el volcado escribe con
`row.save_base(update_fields=names)`, la capa de persistencia de Django sin la
sobrescritura de `save()`, que conserva `auto_now` y las señales. Mantiene lo
que el volcado necesita de la cadena: una sola lectura de reloj por escritura
(`SAVE_NOW`) y, en un `BaseModel`, retirar las marcas de sucio de lo escrito.
Deja fuera, como `_write` en la fuente, el chequeo de compañía, el despacho de
inversos y la lógica de negocio de cada `save()`.

### En los modelos: el alta de los calculados es del ORM

`CrmLead.save`, `SaleOrderLine.save` y `AccountAccount.save` ya no calculan
en alta los campos que el ORM resuelve (precompute en `pre_save`, el resto con
el marcado de creación); en modificación se conservan. `CrmLead` lo
justificaba con «aquí ese motor no existe», que dejó de ser cierto.
`SaleOrder` ya sólo recalculaba al cambiar la empresa, y `AccountMoveLine`
no duplica porque la asignación de `save()` cuenta como dada y el pase no
recalcula un precompute editable dado.

Anulaciones, cada una tumba exactamente su prueba: volcar por `save()`
(lead y cuenta), cálculo en alta de `CrmLead` (lead), de `SaleOrderLine`
(línea), de `AccountAccount` (cuenta); retirar «la asignación cuenta como
dada» (línea de asiento).

### Defecto vecino destapado: las extensiones pierden `@api.depends`

`AccountPaymentMethodLine._compute_name` declara
`@api.depends('payment_method.name')`, pero `account_payment` lo sustituye
con `setattr` por una función sin decorador, y el registro le da cero
dependencias: el campo no se recalcula ni en alta ni cuando cambia el nombre
del método. La fuente une las dependencias de todas las sobrescrituras del
MRO (`odoo19c: odoo/orm/fields.py:584-599`). Aquí las extensiones se instalan
con `setattr`, `chain_method` o `wrap_method`, y ninguno las une: los dos
últimos usan `functools.wraps`, que copia sólo las de la función nueva. Es un
contrato del núcleo; queda como unidad propia (`plan.jsonl`,
`orm-extension-depends-merge-0485`). Por eso la prueba de conteo de esa línea
se retiró de esta unidad: no medía el mecanismo de alta.
