# `Field.index` = `btree_not_null` y `trigram` en campos ordinarios

Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`.

## Contrato

`Registry.check_indexes` (`odoo/orm/registry.py:805-892`), por cada campo
almacenado con columna de un modelo `_auto` y no abstracto, con nombre
`make_index_name(tabla, campo)` = `{tabla}__{campo}_index`
(`odoo/tools/sql.py:779-781`):

| `index` | método | expresión | condición |
|---|---|---|---|
| `True`, `'btree'` | btree | `"col"` | — |
| `'btree_not_null'` (no dependiente de empresa) | btree | `"col"` | `"col" IS NOT NULL` |
| `'btree_not_null'` + `company_dependent` | btree | `("col" IS NOT NULL)` | `"col" IS NOT NULL` |
| `'trigram'` (si `has_trigram`) | gin | `"col" gin_trgm_ops`, envuelto en `unaccent` si es indexable; `jsonb_path_query_array(…)::text` si es traducible | — |

Un campo traducible con índice distinto de `trigram` no se indexa (aviso).
Consumidor de prueba en la referencia: `test_orm.message.body =
fields.Text(index='trigram')` (`test_orm/models/test_orm.py:143`) y
`test_orm/tests/test_index_method.py`.

## Kaupamex antes del cambio

- `Registry.check_indexes` y `_index_shape` están portados
  (`src/orm/registry.py:2700-2800`), pero el esquema lo llevan las migraciones
  de Django y `init_models` no corre sobre él (`fields_company_dependent.py:222`).
- Ya resuelto: `True`/`'btree'` → `db_index` (H-API-1199);
  `company_dependent` + `btree_not_null` → `Meta.indexes` (H-API-1200).
- Hueco: un campo ordinario con `'btree_not_null'` o `'trigram'` no recibe
  índice. Medido: 0 campos lo declaran como argumento hoy; los puertos que lo
  necesitaban lo escribieron a mano en `Meta.indexes` (`website.py:318`,
  `sale/models/analytic.py:64`) y los comentarios lo citan. `test_orm.message`
  no tiene `body`.

## Decisión

- En `_field_contribute_to_class`, para un campo concreto que no es
  dependiente de empresa, de un modelo no abstracto: `'btree_not_null'` →
  `models.Index(fields=[nombre], condition=Q(nombre__isnull=False))`;
  `'trigram'` → `GinIndex(OpClass(F(nombre), 'gin_trgm_ops'))`. Se añaden a
  `Meta.indexes` y a `original_attrs['indexes']`, como en H-API-1200.
- El nombre lo da una sola función, compartida con `_not_null_index`, para que
  el truncado a 30 caracteres (`models.E034`) no se duplique.
- Divergencia declarada: el `unaccent` del trigram depende de la base
  (`has_unaccent == INDEXABLE`) y una migración no la conoce al declararse. El
  índice se crea sin `unaccent`; `check_indexes`, si llega a correr, lo ve con
  el método correcto (`gin`) y no lo rehace.
- Campo traducible: no aplica todavía (`translate=True` se anota sin columna
  `jsonb`, `models.py:1997-2004`); sin índice, como pide la referencia para el
  caso distinto de `trigram`.
- Se porta `body = fields.Text(index='trigram')` a `test_orm.message`, con su
  migración: es el portador de la referencia, y además desbloquea
  `_onchange_messages` de `test_orm.discussion`.

## Pruebas

1. `body` de `test_orm.message`: en `pg_indexes` existe
   `test_orm_message__body_index` con `USING gin` y `gin_trgm_ops`.
2. Modelo sonda con `isolate_apps`: el SQL que emite
   `schema_editor(collect_sql=True).create_model` lleva
   `WHERE ("col" IS NOT NULL)` para `btree_not_null` y `USING gin` para
   `trigram`; nada para `index=False`.
3. Control de anulación: retirar la rama de cada valor tumba su caso.
