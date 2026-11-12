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
