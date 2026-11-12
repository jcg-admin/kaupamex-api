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

## Corrección del conjunto protegido (segunda unidad)

Las tres desviaciones de arriba se cierran con una sola regla,
`_protected_on_create(model, given)` en `src/orm/models.py`, que usan las dos
vías de alta:

- un calculado dado queda protegido sólo si es editable o precompute;
- con él, todo su grupo (`_computed_group`, ≙ `field_computed.get(field,
  [field])`);
- los precompute que el llamador no dio también, porque
  `_add_precomputed_values` los añade a `vals` antes de la condición.

`BaseModel.create` tenía la misma desviación (`protected.add(field)` sin
grupo y sin los precompute añadidos): ahora usa el grupo y la regla.

### Cuatro defectos que la medición destapó por el camino

1. **Terna caducada en `post_save`.** `post_save` corre dentro de
   `Model.save`, antes de que `BaseModel.save` rehaga `_ids` con el pk nuevo.
   `record_ids(instance)` daba `(None,)` y la protección no cubría la fila.
   El receptor rehace la terna antes de proteger.
2. **Valores asignados antes del primer `save()`.** `_explicit_values` se
   captura en `post_init`; `r = M(); r.start = 5; r.save()` no contaba
   `start` como dado y el cómputo de creación lo pisaba (medido: 5 → 0).
   `FieldDescriptor.__set__` añade el nombre cuando la fila está sin guardar
   y su constructor ya terminó.
3. **Recómputo de una fila sin guardar.** Una fila de Django sin guardar se
   nombra con id `None`, no con `NewId`. `_recompute_native_recordset`
   armaba el lote con `browse(None)` y `compute_value` llamaba `sudo()`; las
   dos reconstruyen por id y devolvían otra fila vacía, así que el cómputo
   leía valores por defecto y los dejaba en la caché compartida de `None`.
   Ahora la fila se calcula sobre sí misma, y el privilegio llega por
   `elevate_privileges`, como ya hacía la rama de filas Django.
4. **Verde falso en `test_employee_map_computes`.** La prueba leía con
   `objects.get` sin volcar, y comparaba `currency_id` cuando las dos
   monedas eran `None`. `_compute_currency_id` leía `line.currency`, que
   `SaleOrderLine` no tiene (su campo es `currency_id`). Corregidos el
   cómputo y la prueba: vuelca antes de leer y usa una moneda real.

### Pendiente registrado, fuera de esta unidad

`SaleOrderLine.save` invoca `_compute_amount` y los dos `_compute_price_reduce_*`
por su cuenta antes de `super().save()`, además del precompute de `pre_save`:
el cálculo corre dos veces antes del INSERT. Es del porte de `sale.order.line`,
no del marcado de creación; la prueba de duplicados mide sólo lo posterior al
INSERT y lo declara.

### Las doce obligaciones y su control

| # | Obligación | Control |
|---|---|---|
| 1 | corre cuando corresponde | `test_employee_map_computes` (cinco casos, volcando) |
| 2 | no actúa sobre modelos históricos | `test_a_historical_creation_is_not_marked` (mide la llamada) |
| 3 | alias correcto | sin control propio: la transacción del ORM es una por proceso; el aislamiento entre bases lo miden `tests/integration/multidb` (declarado en la cabecera del archivo de pruebas) |
| 4 | sin transacciones mezcladas | `test_a_rolled_back_creation_leaves_no_pending_marks` |
| 5 | sin duplicados vía `_create` | `test_orm_create_marks_the_creation_once` |
| 6 | respeta los valores explícitos | `test_an_explicit_editable_computed_value_is_kept`, `..._readonly_..._is_recomputed`, `test_a_value_assigned_before_the_first_save_counts_as_given` |
| 7 | dependencias relacionales | `test_changing_the_line_price_recomputes_the_stored_price`, `test_the_cost_follows_the_employee_hourly_cost` |
| 8 | orden | grupo antes que dependientes: `test_*_protects_the_whole_computed_group` |
| 9 | rollback | igual que 4 |
| 10 | sin efectos laterales en precompute | `test_django_create_computes_a_precompute_once` |
| 11 | sin omisiones | `test_the_rule_protects_every_precompute_even_when_not_given` |
| 12 | caché y lecturas coherentes | `test_construction_values_are_not_recorded_twice` y el volcado previo a cada lectura |

### Anulaciones

Cada guarda se retiró y cayeron exactamente sus casos (`nullify.sh`):

| Guarda retirada | Casos que caen |
|---|---|
| expansión al grupo | los dos de grupo + la regla de grupo (3) |
| precompute en la regla | duplicado Django + regla de precompute (2) |
| `not readonly` | readonly recalculado + regla readonly (2) |
| `ORM_CREATE_INSERTING` | marcado único vía `_create` (1) |
| rehacer la terna | grupo por Django (1): sólo un `BaseModel` lleva `_ids` |
| guarda de modelo histórico | histórico no marcado (1) |
| `line.currency_id` | precio y moneda desde la línea (1) |
| asignación tras `__init__` como dada | asignación antes del primer `save` (1) |
| sin `sudo()` para id `None` | ídem (1) |
| recómputo en sitio para id `None` | ídem (1) |

La guarda de modelo histórico no se veía midiendo el resultado: el modelo
histórico declara los mismos calculados, pero sus campos clonados no tienen
disparadores en el registro vivo y `modified` no deja marcas aunque se le
llame. Por eso el control mide la llamada.

*Métrica:* valores persistidos tras el volcado, llamadas a `modified` y al
método de cómputo, marcas pendientes en la transacción.
*Ciega a:* el alias de base de datos (ver obligación 3) y a los modelos que no
declaran calculados almacenados.

## Corrección de una afirmación y duplicado medido (2026-11-12)

**La afirmación que se corrige.** El mensaje de `7f23c97c` y la primera
versión de este diseño decían que los calculados almacenados de una fila
creada por Django «no se calculaban nunca», con `CrmLead` como ejemplo. Lo
cierto es más estrecho: no se **marcaban**. `CrmLead.save` llama él mismo
`_compute_stored_fields()` antes del INSERT, y sus valores ya eran correctos.
Medido: con el receptor anulado, los 22 calculados de una iniciativa con
cliente salen iguales; sólo cambia `date_last_stage_update`, que es la hora.

**El duplicado que eso produce.** Un barrido AST de los `save()` del árbol
encuentra 35 que invocan métodos `_compute_*` por su cuenta. Ocho de ellos son
modelos con calculados almacenados declarados, y en esos el marcado de
creación vuelve a ejecutar el cálculo tras el INSERT:

| Modelo | Cómputos que `save()` invoca |
|---|---|
| `account.AccountAccount` | `_compute_account_tags`, `_compute_account_type`, `_compute_internal_group` |
| `account.AccountMoveLine` | `_compute_balance`, `_compute_partner_id`, `_compute_product_uom_id` |
| `account.AccountPaymentMethodLine` | `_compute_name` |
| `base.ResPartner` | `_compute_complete_name`, `_compute_lang`, `_compute_partner_share`, `_compute_user_id` |
| `base_automation.BaseAutomation` | `_compute_action_server_ids` |
| `crm.CrmLead` | `_compute_stored_fields` |
| `sale.SaleOrder` | `_compute_validity_date` |
| `sale.SaleOrderLine` | `_compute_amount`, `_compute_price_reduce_taxexcl`, `_compute_price_reduce_taxinc` |

Los valores coinciden (el gate completo sale verde), pero la obligación 5 —el
mecanismo no programa dos veces el mismo cálculo— no se cumple en estos ocho.
Un campo editable asignado así queda protegido desde esta unidad, porque la
asignación sobre una fila sin guardar cuenta como dada; los readonly no.

**Sucesor: siguiente unidad.** En cada uno de los ocho, retirar del `save()`
la llamada eager a los cómputos que el ORM ya declara, con prueba de conteo
por modelo y su anulación. La vía de modificación ya está cubierta por el ORM:
asignar sobre una fila guardada pasa por `FieldDescriptor.__set__`, que llama
`modified` y marca los dependientes. Los otros 27 `save()` invocan cómputos de
campos que no se declaran calculados; su veredicto es parte del porte de cada
modelo.

Matriz de los modelos con calculados almacenados:
`outputs/stored-compute-models-20261112.tsv`, producida por
`probes/stored_compute_matrix.py` (23 modelos hoy; las 21 de la medición
anterior más modelos de `test_orm`).

*Métrica:* llamadas `self._compute_*` en el cuerpo de cada `save()` (AST), y
valores persistidos de `CrmLead` con y sin receptor.
*Ciega a:* un cómputo invocado indirectamente desde `save()` por un método
auxiliar con otro nombre.

## Auditoría de las cinco pruebas: columnas que faltaban

| Prueba | Estado inicial que necesita | Operación aislada | Cuándo vuelca la fuente | Defecto que detectaba antes | Defecto que detecta ahora |
|---|---|---|---|---|---|
| `…_touching_debit_recomputes…` | línea con `balance` ya calculado y sin pendientes | `modified(['debit'])` tras forzar 0 por SQL | tras `create` (alta) y tras la marca | que la marca no moviera el valor | lo mismo, y además que el alta deje `balance` sin calcular (sin el volcado previo el valor sale del alta, no de la marca) |
| `…_without_touching_it…` | ídem | volcado sin marca | ídem | que el volcado escribiera sin marca | ídem; sin el volcado previo pasaría por la razón equivocada: el pendiente del alta reescribe 60 |
| `test_compute_writes_m2m::…_relation_is_left_alone` | cuenta con `tags` ya calculado | volcado sin marca sobre un M2M calculado | ídem | que el volcado tocara la relación | ídem |
| `…only_the_probes_of_that_owner…` | dos sondas sin pendientes | `modified` sobre un dueño | ídem | que se marcaran sondas de otro dueño | ídem; sin el volcado previo la otra sonda aparece por su alta |
| `…backward_walk_is_skipped` | sonda sin pendientes | `modified(create=True)` | ídem | que el recorrido hacia atrás corriera en alta | ídem |

Ninguna de las cinco debería observar el valor calculado inmediatamente
después del alta: las cinco miden una operación posterior y presuponen un
punto de partida estable, que en la fuente es `create` seguido del volcado de
la transacción. El volcado previo reproduce ese estado; no oculta un valor
incorrecto.

**Control pendiente** (se ejecuta cuando la base esté libre): retirar
`_settle_creation()` de cada una y comprobar que el fallo resultante nombra el
pendiente del alta (el campo calculado de la fila creada) y no otro valor.
Si alguna fallara por otra causa, el volcado estaría ocultando un defecto y
la prueba se corrige en el ORM, no en la prueba.
