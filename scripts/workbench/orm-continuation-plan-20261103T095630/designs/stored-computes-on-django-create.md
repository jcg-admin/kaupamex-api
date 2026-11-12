# Los cálculos almacenados de un registro creado por Django

Destapado por el paso 1 de `project-sale-line-employee-map-port.md`.

## Lo medido

En la fuente, `create()` inserta y llama a
`records.modified(self._fields, create=True)` bajo `env.protecting` de los
campos que trae `vals` (`odoo19c: odoo/orm/models.py`, `_create`): todo
cálculo almacenado de la fila nueva queda pendiente y el volcado lo
calcula. Aquí eso lo hace sólo `BaseModel._create` (`orm/models.py:1250`).

Un registro creado por el camino de Django —`save()` de una instancia
nueva, `objects.create`— no pasa por ahí. Medido con un probe sobre
`project.sale.line.employee.map`: el costo calculado vale 0 tras crear y
sigue en 0 tras `env().flush_all()`. La población, medida sobre los modelos
vivos: **21** modelos con cálculos almacenados sin `precompute`; **8** no
tienen `create` del ORM (`crm.CrmLead` con 25 cálculos, `sale.SaleOrder`,
`base.IrRule`, …) y los otros 13 lo tienen pero también se crean por Django.

## Corrección (CONSTRUYE con las primitivas del ORM)

Un receptor `post_save` con `created=True`, hermano del `pre_save` que ya
corre los `precompute` (`orm.models._run_precompute`):

1. llama a `modified(registro, campos, create=True)`, como `_create`;
2. bajo `env().protecting` de los cálculos que el llamador dio de forma
   explícita (`_explicit_values`), igual que `vals` en la fuente;
3. no actúa cuando la inserción viene de `BaseModel._create` —que ya lo
   hace—, marcado con una variable de contexto durante su bucle de
   inserción; ni con `raw` (fixtures), ni sobre modelos históricos.

## Verificación

- RED/GREEN en `tests/unit/sale_timesheet/test_employee_map_computes.py`
  (crear con línea de venta da su precio; crear con empleado da su costo).
- Anulación: sin el receptor caen exactamente los casos de creación.
- Gate completo: el cambio es transversal (21 modelos).

## Contrato exacto de la fuente (odoo-tools `abe4040ec1`)

`BaseModel.create` (`odoo19c: odoo/orm/models.py:4665-4690`) reparte cada
`vals` y arma `data['protected']`: **sólo** los campos calculados presentes
en `vals` que son editables o precalculados —`field.compute and (not
field.readonly or field.precompute)`— y, por cada uno, el **grupo** entero
que calcula el mismo método (`self.pool.field_computed.get(field,
[field])`). `_add_precomputed_values` (`:4810-4846`) mete antes en `vals`
los precalculados que faltan, así que quedan protegidos también.
`_create` (`:4930-4933`) llama a `records.modified(self._fields,
create=True)` bajo `env.protecting(protected)`.

La primera versión del receptor protegía todo calculado nombrado (incluso
`readonly`), sin el grupo ni los precalculados: tres desviaciones que se
corrigen contra esta cita.

## Auditoría de las cinco pruebas cuyo arranque cambió

En las cinco, la fila de partida se crea con `objects.create` y el caso
controla una marca o un volcado POSTERIOR. Antes del receptor la creación no
dejaba pendientes (el defecto); con él deja los mismos que deja la fuente.

| Prueba | Propósito | Pendiente nuevo tras crear | Fuente | `_settle_creation` |
|---|---|---|---|---|
| `test_compute_wiring::…_touching_debit_recomputes…` | `modified(['debit'])` marca y el volcado escribe `balance` | `balance` de la línea | marca al crear; un `flush` posterior calcula 60 | vuelca lo del alta antes del `UPDATE` que fija 0: el caso sigue midiendo que la marca de `debit` mueve el valor |
| `test_compute_wiring::…_without_touching_it…` | sin `modified`, el volcado no escribe | ídem | ídem | ídem: sin él, el pendiente del alta reescribía 60 y el control no discriminaba |
| `test_compute_writes_m2m::…_relation_is_left_alone` | sin marca, el volcado no toca el M2M | `tags` de la cuenta | ídem | ídem |
| `test_modified_engine::…only_the_probes_of_that_owner…` | `modified` marca sólo las sondas de ese dueño | `owner_label` de las dos sondas | ídem | sin él, la otra sonda aparecía por su alta, no por la marca medida |
| `test_modified_engine::…backward_walk_is_skipped` | con `create=True` no se recorre hacia atrás | `owner_label` de la sonda | ídem | ídem |

Ninguna aserción se retira ni se debilita: el volcado previo reproduce el
estado que la fuente tendría tras `create` + `flush`, que es el punto de
partida que cada caso presupone. Los controles positivos de los mismos
archivos (`test_without_create_the_same_call_does_mark`, y los que exigen
que la marca sí mueva el valor) siguen pasando.

Controles que faltan y se añaden con la corrección: valores explícitos
editables protegidos y `readonly` no protegidos; grupo de un mismo
`compute`; sin duplicado por el camino de `_create`; rollback sin marcas
huérfanas; alias.
