# Diseño — `groups` del campo al escribir (TASK-API-0485)

Fecha: 2026-11-09T01:00:24.

## Contrato (odoo19c)

`BaseModel.write` llama a `_check_field_access(field, 'write')` por cada
nombre (`odoo/orm/models.py:4377-4382`); la asignación directa
`record.campo = v` entra por `Field.__set__` → `write`, así que rechaza
igual. Medido con `tests/fixtures/reference_field_groups.py` sobre
`test_orm.model.some_access` (`test_orm.py:1814-1830`):

| Actor | Campos que rechazan `write` y asignación |
|---|---|
| plain (sólo el grupo con ACL) | d, e, g, h, j, k |
| rich (+ `base.group_erp_manager`) | j, k |

`a` (sin `groups`) e `i` (`!base.group_portal`) se escriben en los dos.

## Aquí

`BaseModel.write` ya hace el mismo bucle (`src/orm/models.py`, método
`write` de `BaseModel`). La duda era la ruta alternativa: la asignación
directa sobre un recordset. Medido: los 32 escenarios de escritura y
asignación coinciden (66 en total con las lecturas).

## Controles pendientes

Anular el bucle de `write` y ver qué cae; si la asignación no cae, buscar su
propia comprobación y anularla también. Se ejecutan cuando termine la suite
completa en curso, que lee `src/orm/models.py`.
