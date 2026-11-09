# Diseño — unidad 4 de `read_group`: valor vacío y posproceso

Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`,
`odoo/orm/models.py`: `_read_group_empty_value`, `_read_group_postprocess_groupby`,
`_read_group_postprocess_aggregate`. No dependen del origen del `Query`: reciben
un spec y los valores crudos de una fila de PostgreSQL.

## Contrato

| Spec | Valor vacío |
|---|---|
| `__count`, `*:count`, `*:count_distinct` | `0` |
| `*:array_agg`, `*:array_agg_distinct` | `[]` |
| relacional o `id`, sin agregado o con `recordset` | el recordset vacío del comodelo (o del propio modelo para `id`) |
| `m2o.campo[:g]` | el valor vacío de `campo[:g]` en el comodelo |
| cualquier otro | `False` |

Posproceso: un relacional (o `id`) se convierte en recordsets de un elemento
que comparten el `prefetch` de todos los ids no nulos; un `NULL` se vuelve el
valor vacío; un `recordset` agregado quita repetidos y nulos conservando el
orden (`unique`) y comparte el `prefetch` de todas las filas.

## Adaptación declarada

`self.env[name]` devuelve aquí la clase y no hay `self.pool`. La fuente construye
con `Model(self.env, ids, prefetch_ids)`; aquí:

- comodelo `BaseModel` → `Model._from_ids(env, ids, prefetch_ids)`, que es el
  constructor de la terna;
- comodelo de Django (`res.users`) → `orm.utils.browse(Model, ids)`, la
  adaptación existente de `browse`; un `QuerySet` no lleva `prefetch`.

Se concentra en un ayudante de módulo, `_read_group_recordset(env, model, ids,
prefetch_ids)`, para no repetir la elección en tres sitios.

## Pruebas (RED)

`tests/unit/orm/test_read_group_postprocess.py` sobre `test_orm.message`
(`discussion` → `BaseModel`, `author` → `res.users` de Django): cada fila de la
tabla, la cadena `discussion.moderator`, el `prefetch` compartido, `NULL` y la
deduplicación del agregado `recordset`.
