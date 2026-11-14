# `hr.employee.public` sobre `BaseModel`

Creado: 2026-11-14T12:09:06 (UTC). TASK-API-0397. Tercer y último tramo de
`basemodel-adoption-hr-core-0397`.

## Búsqueda previa

Adopción de `BaseModel` (REUSE). La vista (`_auto = False`, `init()`) no
cambia: la herencia es Python. Su fila de ACL ya la carga el manifiesto de
`hr` y coincide con la fuente (`base.group_user`, sólo lectura).

## Medido aquí (`bf1116db`)

La clase derivaba de `models.Model`. Con `models.BaseModel`: `tests/unit/hr`
e `integration/hr`, 182 passed; los consumidores en otros directorios, 77
passed y los 15 errores de `test_multidb_isolation`, que exigen base
desechable.

## RED y anulación

Dos casos (es `BaseModel`; un interno lee y no escribe), escritos tras la
base nueva: con la base anterior caen los dos.

## Lo que esta unidad no cierra

Nada del grupo B: con este tramo, ningún modelo de `hr` queda fuera de
`BaseModel` (medido con `issubclass` sobre el registro antes del commit).
