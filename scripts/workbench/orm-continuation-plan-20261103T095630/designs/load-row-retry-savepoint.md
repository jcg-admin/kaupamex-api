# El reintento fila a fila de `load` vuelve a su punto de retorno

TASK-API-0485. Autoridad: odoo-tools `abe4040ec1`.

## Contrato de la fuente

`BaseModel.load` (`odoo19c: odoo/orm/models.py:895-1040`) intenta el lote en
un `cr.savepoint()`; si falla, reintenta fila a fila. Cada fila que la base
rechaza se registra como mensaje (`psycopg2.Warning` → aviso;
`psycopg2.Error`, `UserError`, cualquier otra → error), se hace
`savepoint.rollback()` y la importación sigue. Tras `_load_records` de cada
fila llama `cr.flush()` para que un error del volcado salga en esa fila.

## El defecto, medido

Un `ir.model.access.csv` cuya fila nombra un modelo sin xml id
(`uom.model_uom_uom`, que no existía porque `Uom` no declaraba `_name`) pierde
`model_id` en la conversión, como en la fuente, y el INSERT la rechaza por
`NOT NULL`. El reintento hacía `savepoint.rollback()` y Django lo rechazaba
con `TransactionManagementError`: una consulta que falla dentro de `atomic`
marca la conexión (`needs_rollback`, `mark_for_rollback_on_error`) y desde ahí
rechaza toda consulta, el `ROLLBACK TO SAVEPOINT` incluido. La importación
moría con el error de la transacción en vez de devolver sus mensajes.

## Corrección

1. `service.db.Savepoint.rollback` limpia `needs_rollback` antes de volver al
   punto, igual que `Atomic.__exit__` (`django/db/transaction.py:273-283`):
   el punto se abrió en este nivel y deshace lo que vino después, el error
   incluido. Es la semántica del `ROLLBACK TO SAVEPOINT` de PostgreSQL que la
   fuente usa.
2. El reintento fila a fila gana las dos piezas que faltaban: el
   `env().flush_all()` tras `_load_records` (≙ `cr.flush()`) y la rama
   `psycopg.Warning` como aviso.

## Pruebas

`tests/unit/orm/test_load.py::TestARowThatFailsInTheBase` (2): la fila
registra dos errores —la conversión y la base, los dos sobre `model_id`, el
segundo por los diagnósticos de PostgreSQL—, `ids` es `False`, nada queda
escrito y la transacción sigue utilizable. Anulación: sin limpiar
`needs_rollback` caen exactamente las 2.

## Lo que no cierra

La rama `psycopg.Warning` y el `flush_all` tras cada fila no tienen prueba
propia: psycopg 3 no eleva avisos como excepciones en el uso corriente, y un
error de volcado por fila exige un cálculo almacenado que falle al volcarse.
Condición de cierre: una prueba con un modelo de `test_orm` cuyo cálculo
almacenado levante al volcarse.
