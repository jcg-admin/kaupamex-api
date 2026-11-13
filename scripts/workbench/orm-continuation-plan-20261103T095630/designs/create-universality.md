# `create` y `default_get` en todo modelo

Creado: 2026-11-13T06:03:00 (UTC). TASK-API-0485. Matriz: `designs/timestamped-copy-contract-matrix.md`.

## Contrato

`default_get`, `_add_missing_default_values`, `create`,
`_prepare_create_values` y `_create` cuelgan de `BaseModel`
(`odoo19c: odoo/orm/models.py:4611-4930` y `default_get`): **todo** modelo
los tiene.

## Estado medido (`3e8e8b17`)

Los lleva `DefaultGetMixin`, declarado a mano por 19 modelos de
`TimeStampedModel` y 6 de sólo Django además de los 63 de `BaseModel`;
`create` falta en 354 de 396 modelos de producción y `_create` en 362.
Tres consumidores ya eligen `create` si existe y caen a `objects.create`
si no: `orm/commands.py:254` y `:354` (comandos x2many) y
`name_create` (`orm/models.py:4716`). Sin `create` toman el camino que
la fuente no tiene: sin defaults, sin `check_access('create')`, sin
`_check_company`.

`_create_result` ya distingue: recordset para `BaseModel`, `QuerySet`
para el resto (`orm/models.py:1124-1142`), así que el valor devuelto no
cambia de forma para los modelos que hoy no derivan de `BaseModel`.

## Decisión

`adopt_create`, misma forma que `adopt_copy`: los seis símbolos de
`DefaultGetMixin` (`default_get`, `_add_missing_default_values`,
`create`, `_create_result`, `_prepare_create_values`, `_create`) que el
modelo no resuelva por su MRO; `class_prepared` y barrido en
`base.apps.ready`. Un `create` propio del modelo gana.

## Pruebas

- RED: `ir.exports` sin `create` ni `default_get`; `name_create` de un
  modelo sin `DefaultGetMixin` no pasa por `create`.
- GREEN: `create([vals])` da el `QuerySet` en orden con los valores.
- Censo: ningún modelo concreto propio sin `create`.
- Anulación: con `adopt_create` inerte caen las tres.
