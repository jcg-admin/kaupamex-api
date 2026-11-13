# `resource` sobre `BaseModel`, con sus FK en la forma de la fuente

Creado: 2026-11-13T22:48:13 (UTC). TASK-API-0397.

## Contrato de la referencia (odoo-tools `abe4040ec1`)

- `resource.calendar`, `resource.calendar.attendance`,
  `resource.calendar.leaves` y `resource.resource` son `BaseModel`.
- `resource/security/ir.model.access.csv`: 8 filas.
- `resource/security/resource_security.xml`: 5 reglas. Tres recorren
  `resource_id.user_id` (las de `base.group_user` sobre
  `resource.calendar.leaves`), una usa `base.group_erp_manager` y dos son
  multiempresa con `company_ids + [False]`.
- `resource/data/resource_data.xml`: el calendario estándar ligado a
  `base.main_company` y `res.company._init_data_resource_calendar`.

## Medido aquí (`342723b0`)

Los cuatro modelos derivan de `TimeStampedModel`. Sus FK se llaman `company`,
`user`, `resource` y `calendar` —forma A—, no `company_id`, `user_id`,
`resource_id` y `calendar_id`. Medido con `orm.domains.to_q` sobre
`resource.calendar.leaves`: el resolvedor traduce el attname, también al
recorrer (`resource_id.user_id` da la subconsulta sobre `U0."user_id"`), así
que las reglas copiadas verbatim resuelven. El renombre a la forma de la
fuente es fidelidad de símbolos, no un bloqueo de esta unidad, y pertenece
al barrido de nombres de FK.

`base.main_company` no existe en este árbol.

## Decisión

1. Los cuatro modelos derivan de `BaseModel`.
2. `security/ir.model.access.csv` y `security/resource_security.xml`, copia
   fiel, en `data` del manifiesto (`designs/security-data-by-manifest.md`).
3. `data/resource_data.xml` es la unidad `resource-data-0397`: depende de
   `base.main_company` y de `_init_data_resource_calendar`.

## Pruebas

Los cuatro son `BaseModel`; las 8 filas y las 5 reglas con su identificador
externo; un usuario interno lee calendarios y no los escribe; lee una
ausencia global y la de su recurso, no la de otro usuario; modifica la de su
recurso y no una global. Anulaciones: las bases a `TimeStampedModel`; los
dos archivos fuera de `data`.

## Fuera de esta unidad

Los ocho FK en forma A de los cuatro modelos pasan a la forma C en la unidad
`resource-fk-names-0397`, con su migración (sólo renombra: la columna se
conserva con `db_column`) y sus consumidores en `hr`, `hr_work_entry` y
`hr_skills`.
