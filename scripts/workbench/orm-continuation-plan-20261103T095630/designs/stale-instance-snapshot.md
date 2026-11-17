# La copia de la instancia sobrevive a `invalidate_recordset`

Fecha: 2026-11-17. Revisión: `05637099` + unidad 3 sin publicar.
Referencia: `odoo19c: odoo/orm/fields.py:1642-1690` (`Field.__get__`) y
`odoo/orm/models.py:6724-6736` (`invalidate_recordset`).

## Lo medido

Sonda sobre `purchase.order.line.qty_invoiced` (calculado y almacenado):

```
A        3.0000   # leído tras flush + invalidate
(se edita la línea de factura: el ORM deja la fila en tocompute)
TOC1     OrderedSet([1832])
invalidate_recordset()
TOC2     OrderedSet([])      # flush_recordset recalculó
DB       4.0000              # y escribió
READ     3.0000              # pero la misma instancia lee 3
```

Un registro nuevo (`line.browse(line.id)`) lee 4.

## Causa

`FieldDescriptor.__get__` (`src/orm/fields.py:1700-1717`) devuelve
`instance.__dict__[attname]` cuando está presente y el campo no es un
calculado sin columna, con el comentario «un valor en el almacén es un valor
vigente». Esa premisa vale cuando el recálculo pendiente lo resuelve la propia
lectura, pero no cuando lo resuelve `flush_recordset` dentro de
`invalidate_recordset`: `_invalidate_cache` (`fields.py:4993-5011`) vacía
`transaction.field_data` y no puede alcanzar las instancias, así que la copia
de Django queda con el valor anterior.

En la fuente no hay copia: un registro no guarda valores y `__get__` lee
siempre de `env.cache`; invalidar deja sin valor a toda instancia de la fila.

`_value_written_by_another_instance` (`fields.py:1525-1560`) ya resuelve la
misma clase de defecto para columnas ordinarias escritas por otra instancia
(`transaction.field_written`), pero excluye los calculados almacenados
(`fields.py:1607`: `field.store and not field.compute and not field.related`).

## Diseño propuesto (no implementado)

Registrar las invalidaciones por campo e id en la transacción
(`transaction.field_invalidated`, análogo a `field_written`) desde
`Field._invalidate_cache`, y en `__get__`, antes de devolver la copia de
`__dict__` para un campo almacenado (calculado o no), descartarla si su fila
fue invalidada después de cargarse, y releer de la base. Controles: la sonda
de arriba como RED; anulación del registro, que debe hacer caer exactamente
ese caso; F2 y F3, porque toca caché y transacción.

## Lo que este diseño no cierra

No hay unidad en `plan.jsonl` para este defecto y desde esta VM no se acuña
TASK (no se escribe en el TaskStore). Su dueño natural es la familia de caché
del ORM (`src/orm/fields.py`, `src/orm/models.py`). Mientras tanto, la
prueba de `qty_invoiced` lee sobre un registro nuevo y lo declara en su
docstring; no se usa `xfail`.
