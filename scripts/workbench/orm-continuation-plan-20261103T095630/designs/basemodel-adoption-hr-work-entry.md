# `hr_work_entry` sobre `BaseModel`, con su seguridad (grupo D de HR)

Creado: 2026-11-14T08:32:21 (UTC). TASK-API-0397. Grupo D de `designs/hr-basemodel-dependencies.md`.

## Búsqueda previa

Autoridad del mecanismo: el ciclo de instalación carga los `data` del
manifiesto (`designs/security-data-by-manifest.md`); precedentes `hr`,
`uom`, `utm`, `sales_team`, `resource`. **REUSE.**

## Contrato de la referencia (odoo-tools `abe4040ec1`)

- `hr.work.entry`, `hr.work.entry.type` y `hr.user.work.entry.employee` son
  `BaseModel`.
- `security/ir.model.access.csv`: 6 filas, una del asistente de
  regeneración.
- `security/hr_work_entry_security.xml`: 3 reglas.

## Medido aquí

- Los tres derivan de `TimeStampedModel`; FK en forma A (`user`, `company`,
  `country`), que el resolvedor de dominios traduce por attname.
- `hr.work.entry.regeneration.wizard` es un `TransientModel` abstracto, sin
  tabla ni fila en `ir.model`: su fila de ACL no tiene destino. Es la misma
  omisión que el CSV de `hr` declara para sus asistentes.
- `ir_rule_hr_work_entry_type_multi_company` evalúa
  `user.env.companies.mapped('country_id')`: exige `res.users` y
  `res.company` sobre `BaseModel`, el bloqueo medido que `hr` ya declara
  (`designs/module-install-cycle.md`, L4e).

## Decisión

Los tres modelos derivan de `BaseModel`; `security/hr_work_entry_security.xml`
(sin la regla de tipo, declarada en su cabecera) e `ir.model.access.csv`
(sin la fila del asistente, declarada en el manifiesto), copia fiel, en
`data`. `data/hr_work_entry_type_data.xml` y `data/ir_cron_data.xml` son la
unidad `hr-work-entry-data-0397`.

## Pruebas

Los tres son `BaseModel`; 5 filas y 2 reglas con identificador externo; un
oficial de RR. HH. crea entradas y no las borra; un usuario interno sólo
escribe su propio filtro de calendario. Anulaciones: bases y manifiesto.
