# TASK-API-0512 — Leer un Many2one diferido no es escribirlo

Fecha: 2026-11-09. Hallazgo: H-API-1210 (`kaupamex-docs@34e261328`).
Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`,
`odoo19c: odoo/orm/fields.py` (`Field.__get__` → `fetch` →
`_insert_cache`; una lectura no llama `modified`).

## Causa medida

Sonda con espía en `orm.models._modified` al leer `child.parent_id` de
`test_orm.model_child_m2o` (columna diferida tras el volcado):

```
fields.py:2143  __get__  -> ForeignKeyDeferredAttribute.__get__
  (Django DeferredAttribute.__get__ -> refresh_from_db(fields=[...]))
models.py:6041  __setattr__
fields.py:2158  __set__  (Many2one: False -> None)
fields.py:1970  __set__  -> instance.modified([field.name])
```

La carga diferida de Django asigna con `setattr`, y
`FieldDescriptor.__set__` la trata como una escritura de negocio: anuncia
`parent_id` y marca `parent.cost` y `child.size1`/`size2`. La guarda
existente («un refresh entrega el mismo valor») no cubre este caso porque
el valor previo falta (diferido).

## Search Existing — REUSE

`FieldDescriptor.__get__` (`src/orm/fields.py:1706-1719`) ya resuelve
exactamente esto para los campos escalares: marca `_orm_building`
alrededor de `super().__get__` (la carga diferida), de modo que el
`__set__` que dispara entra en el tramo de carga (`_insert_cache`, sin
`modified`, sin marca de sucio). El descriptor del `Many2one`
(`ForeignKeyFieldDescriptor.__get__`, `:2129-2142`) llama
`ForeignKeyDeferredAttribute.__get__` **sin** esa marca. Decisión: REUSE
del mismo mecanismo en el descriptor del `Many2one`; ningún mecanismo nuevo.

## Casos (RED)

1. Tras crear y volcar, leer `child.parent_id` deja `tocompute` vacío.
2. El valor leído es el de la base (el id del padre).
3. Control: asignar `child.parent_id = otro` sí anuncia y marca
   `child.size1`.

Anulación prevista: retirar la marca en el descriptor del `Many2one` tumba
1; 2 y 3 no dependen de ella.

## RED, GREEN y anulación (2026-11-09)

- RED sobre `1b6fde6c` + TASK-API-0511 sin commitear: `1 failed, 2
  passed` — cae el 1 con las tres marcas de la sonda (`parent.cost`,
  `child.size1`, `child.size2`); 2 y 3 ya pasaban.
- GREEN: `3 passed`; con los de TASK-API-0511, `7 passed`.
- Anulación: sin la marca `_orm_building` en el descriptor del `Many2one`
  cae exactamente el 1; restaurada y verificada con `cmp`.
