# La transacción del ORM es la del cursor del entorno

## Lo medido (2026-11-12, sobre `7911b42b`)

`get_transaction()` devolvía siempre la transacción colgada de
`connections['default']`, y `Environment.transaction` delegaba en ella. Un
entorno sobre otro alias marcaba, protegía y volcaba en la transacción de
`default`:

- `env['test_orm.shared.compute'].create({...})` dentro de
  `with Environment(alias, ...)`: las marcas de `start`/`end` aparecían en la
  transacción de `default`.
- `SharedCompute.objects.using(alias).create(...)` fuera de todo entorno: el
  receptor de `post_save` marcaba en `default`.

La obligación 3 de `stored-computes-on-django-create.md` (alias correcto) se
había declarado cubierta por `ci-multidb`. No lo estaba: ninguna prueba de
ese gate crea filas con calculados almacenados en un alias distinto.

## Contrato de la fuente

`Environment.__new__` (`odoo19c: odoo/orm/environments.py:70-80`) fija
`self.transaction = cr.transaction`, creándola si falta. Una transacción por
cursor; un entorno sobre otro cursor tiene otra transacción, y `_flush`
escribe por `self.env.cr`.

## Corrección

1. `get_transaction()` resuelve el cursor del bloque activo (`_cr`,
   `get_current_cr()`), y `default` fuera de todo bloque.
2. `Environment.transaction` devuelve la transacción de su propio
   `db_alias`, aunque el entorno no esté abierto.
3. El receptor de `post_save` deriva el entorno del alias de la fila
   (`instance._state.db`) con `env(cr=alias)` y marca dentro de él.

## Controles

`tests/integration/test_orm/test_creation_marks_on_alias.py`, sobre un alias
de sondeo con conexión y transacción propias (la técnica de
`test_env_alias_recordset`): la fila no existe para `default` hasta el commit.

| Guarda retirada | Casos que caen |
|---|---|
| `get_transaction` por `_cr` | creación Django y creación ORM en alias (2) |
| `Environment.transaction` por `db_alias` | entorno sin abrir con su transacción (1) |
| entorno derivado en el receptor | creación Django en alias (1) |

*Métrica:* marcas por transacción de conexión y valores leídos por cada
conexión.
*Ciega a:* dos bases físicas distintas (el alias apunta a la misma base) y a
código que guarde una referencia a una transacción antes de entrar en otro
entorno.
