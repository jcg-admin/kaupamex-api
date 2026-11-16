# Calculados y related sin columna sobre registros de `new()`

Fecha: 2026-11-16T18:27:59 · unidad `orm-nonstored-compute-on-new-records-0397` ·
TASK canónica `TASK-API-0397` («Construir BaseModel propio desde el contrato
medido de la referencia», `in_progress`; verificado en el store del
proveedor en sólo lectura, columna `citation_id`).

## Síntoma medido

Leer cualquier calculado o related sin columna sobre un registro de
`new()` levantaba `ValueError: Compute method failed to assign …`.
Medido fuera de purchase: `test_orm.multi.name` (related
`partner.name`) y `purchase.order.lock_confirmed_po` (related
`company_id.po_lock`), además de los related de `purchase.order.line`.

## Contrato de la fuente (odoo19c: odoo/orm/fields.py)

- `Field.__get__` (`:1642-1806`): en un fallo de caché sobre un
  registro nuevo sin origen, un campo calculado se calcula con
  `compute_value(recs)`, y si después falta en la caché un campo
  `readonly` sin columna, el error es exactamente el observado
  (`:1752-1755`).
- `compute_value` (`:1897-1918`): `records.sudo()` si
  `compute_sudo` —con los MISMOS ids; la caché es de la transacción— y el
  cómputo corre bajo `env.protecting(fields, records)`.
- `__set__` (`:1807-1841`): un id protegido va a `Field.write`.
- `Field.write` (`:1501-1518`) descarta con `_filter_not_equal`
  (`:1577-1586`) **sólo** los ids cuyo valor en caché ya es el mismo; un
  `NewId` es una clave de caché como cualquier otra.
- Una relación vacía se lee como el valor nulo del campo: el recordset vacío
  del comodelo (`convert_to_record(convert_to_cache(False))`).

## Causa demostrada

`orm.fields._filter_not_equal_ids` filtraba `if id_ and …`. La guarda
existía para excluir el `pk` `None` de una fila de Django sin guardar
—con ese `None` como clave, el valor de una fila le contestaba a la
siguiente (medido entonces: el `pre_save` de un `DateField` leía la
caché de otra fila)—. Pero `NewId` también es falso (`__bool__`
devuelve `False`, `orm/identifiers.py:26`, como en la fuente), así que
la guarda descartaba también el registro de `new()`. Bajo protección, la
asignación del cómputo pasa por `Field.write` y se perdía entera: la
caché quedaba vacía y `__get__` levantaba.

Medido con un espía sobre `field.compute`: el cómputo recibía la misma
instancia y el mismo entorno, corría, y tras él ni la caché ni el
`__dict__` tenían el valor; llamado fuera de `protecting()`, el mismo
cómputo sí lo dejaba (la ruta de `__set__` para `NewId` no protegido
siembra la caché directamente).

### Hipótesis previas, descartadas por medición

1. «`sudo()` pierde el registro en memoria»: extender la guarda de
   `compute_value` para no aplicar `sudo()` a un `NewId` no cambió el
   resultado. El espía confirma que el cómputo recibía la instancia original.
2. «La exclusión de `NewId` en la rama del `__dict__` de `__get__`»:
   retirarla no cambió el resultado, porque el `__dict__` también estaba
   vacío — la escritura no llegaba a ninguna parte.

Las dos se revirtieron; ninguna se conserva.

## Dos defectos más que el arreglo destapó

- **FK requerida sin asignar.** Con la caché ya funcionando, un related que
  cruza `order_id` (`null=False`) sobre una línea nueva levantaba
  `RelatedObjectDoesNotExist`: es el descriptor de Django, que exige la FK
  al LEER. En la fuente esa obligación es del guardado; la lectura da el
  valor nulo. Propietario: `orm.models._forward_get`, sólo para `NewId`
  (una fila persistida conserva el error de Django).
- **x2many nulo.** `null_record_value` devolvía `None` para todo
  relacional; un related que termina en Many2many sobre un eslabón vacío
  leía `False`. La fuente lee la colección vacía: el recordset vacío del
  comodelo, o el `QuerySet` vacío si el comodelo es de Django (la misma
  forma que `_end_of_chain` da cuando hay valor).

## Correcciones en el propietario del ORM

| Defecto | Propietario | Contrato de la fuente |
|---|---|---|
| `NewId` descartado como clave | `orm.fields._filter_not_equal_ids` (`if id_ is not None`) | `_filter_not_equal` (`:1577-1586`) |
| FK requerida sin asignar sobre `new()` | `orm.models._forward_get` (sólo `NewId`) | valor nulo del campo (`:1793-1806`) |
| x2many calculado leía la tupla de caché | `orm.fields_relational._many2many_convert_to_record` | `_RelationalMulti.convert_to_record` (`fields_relational.py:643-653`), con filtro `active` |

Un cuarto cambio —`null_record_value` devolviendo la colección vacía de un
x2many— se probó y se **retiró**: su anulación dejaba todo en verde, porque
`convert_to_cache` y `convert_to_record` ya normalizan el vacío. Código sin
control que lo discrimine no se conserva.

## Cobertura (`tests/unit/orm/test_new_record_nonstored_compute.py`)

Related con Many2one presente y cadena de dos eslabones; related sobre
eslabón vacío; related Many2many con varios registros y vacío; calculado sin
columna que depende de una relación (`root_categ`); dependencia modificada
antes de guardar; `sudo()` y `with_env()`; identidad `NewId`, caché y cero
`INSERT`/`UPDATE`/`DELETE` durante la lectura; FK requerida vacía
(`purchase.order.line.order_id`) y el error de Django conservado sobre una
fila persistida; related que termina en un Many2many de Django; los dos
consumidores reportados (`test_orm.multi.name`,
`purchase.order.lock_confirmed_po`); y las dos mitades de la guarda de clave
(`None` fuera, `NewId` dentro). El `xfail` de
`test_line_currency_id_is_empty_without_an_order` se retiró: es una prueba
ordinaria.

## Controles de anulación (medidos)

- `if id_` (la guarda vieja): caen 9 casos, todos de lectura sobre `new()`.
- Sin guarda alguna: cae exactamente el caso de la clave `None`.
- Sin la rama de `_forward_get`: caen exactamente los 2 de FK requerida.
- Sin `ManyToManyField.convert_to_record`: caen exactamente los 2 de
  related Many2many hacia `BaseModel`.
- `price_unit_discounted` calculado en `float`: cae exactamente el caso de
  precisión decimal (`99.99` con `12.5 %` → `87.49125`).

## Lo que no cierra

- `price_unit_product_uom` pasa por `float`: la fuente lo declara `Float`
  y `uom._compute_price` opera en `float`, así que es el contrato, no una
  conversión implícita.
