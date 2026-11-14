# `hr_recruitment`: los Many2many de entrevistadores con su nombre de la fuente, y la regla del entrevistador

Creado: 2026-11-14T10:00:41 (UTC). TASK-API-0397. Unidad
`recruitment-interviewer-fields-0397`, sucesora de
`basemodel-adoption-hr-recruitment-0397` (`5b6ef419`).

## Búsqueda previa

- Nombre y tabla de un Many2many: `orm.fields_relational.Many2many` ya
  acepta `relation`/`column1`/`column2` posicionales y construye
  `Many2manyField` (REUSE).
- Carga de reglas: seguridad por manifiesto
  (`designs/security-data-by-manifest.md`, REUSE). El dominio lo traduce
  `orm.domains.to_q`; `job_id` ya resuelve por el attname de la FK `job`.
- Adopción de `BaseModel`: el patrón de las unidades de utm, sales_team,
  resource y hr_work_entry (REUSE).

Ningún mecanismo nuevo. Veredicto: REUSE. GapClass: A, porque bloquea una
regla de seguridad de la fuente. ExecuteNow: yes.

## Contrato (odoo-tools `abe4040ec1`, `odoo19c:`)

- `hr_recruitment/models/hr_job.py:64-70`:
  `interviewer_ids = fields.Many2many("res.users", ...)`, sin `relation`. La
  fuente deriva la tabla en `odoo/orm/fields_relational.py:1291-1295` como
  `'%s_%s_rel' % sorted(tablas)`, es decir `hr_job_res_users_rel`, con
  columnas `hr_job_id` y `res_users_id`.
- `hr_recruitment/models/hr_applicant.py:125-127`:
  `interviewer_ids = fields.Many2many('res.users',
  'hr_applicant_res_users_interviewers_rel', ..., index=True, copy=False)`.
  Sus columnas derivan igual: `hr_applicant_id` y `res_users_id`.
- `hr_recruitment/security/hr_recruitment_security.xml:49-60`:
  `hr_applicant_interviewer_rule`, con
  `['|', ('job_id.interviewer_ids', 'in', user.id), ('interviewer_ids', 'in', user.id)]`,
  `perm_create=False`, `perm_unlink=False` y el grupo
  `group_hr_recruitment_interviewer`.

## Medido aquí (`5b6ef419`)

- `hr.job.interviewers`: lo cuelga `extend_model` desde
  `addons/hr_recruitment/models/hr_job.py`, en la migración
  `hr/0010`, con la tabla que nombra Django.
- `hr.applicant.interviewers`: en `hr_recruitment/0001`, con la tabla que
  nombra Django y `db_index=True`.
- Consumidores: los dos modelos, `res_users.py` del addon y las dos
  migraciones. Ningún test nombra `interviewers`.
- `HrApplicant` deriva de `MailThread, MailActivityMixin, UtmMixin,
  TimeStampedModel`: no es `BaseModel`, así que una regla sobre él no filtra.
  `HrJob` (addon `hr`) tampoco lo es, pero la regla sólo lo recorre como
  lookup.

## Hipótesis (sonda pendiente): la sincronía de entrevistadores de `save()` no se dispara

`HrApplicant.save()` (`addons/hr_recruitment/models/hr_applicant.py:585-662`)
lee los entrevistadores antes de `super().save()` y otra vez después, y
llama a `_create/_remove_recruitment_interviewers` y a `message_notify` con
la diferencia. Un Many2many se escribe por su gestor (`.add`/`.set`), que no
pasa por `save()`; `save()` tampoco toca la tabla intermedia. Las dos
lecturas devuelven el mismo conjunto por construcción: el código existe y no
se dispara. La fuente lo hace en `create`/`write`
(`odoo19c: hr_recruitment/models/hr_applicant.py:617-700`), con
`old_interviewers` leído antes de `super().write(vals)` y la rama
`'interviewer_ids' in vals`.

## Decisión — dos unidades

1. **`recruitment-interviewer-fields-0397` (esta).** Forma C:
   `interviewers` → `interviewer_ids` en los dos modelos, con la `relation`
   y las columnas de la fuente. Migraciones: `RenameField` más `AlterField`
   a `Many2manyField`, que renombra la tabla intermedia y sus columnas sin
   perder filas. Exige ci-multidb. Los consumidores (`save()`, `res_users.py`,
   `hr_job.extended_interviewer_ids`) cambian de nombre, no de forma.
2. **`hr-applicant-basemodel-0397` (sucesora).** `hr.applicant` sobre
   `BaseModel`, con `create`/`write` portados como en la fuente en lugar de
   `save()`, lo que deja viva la sincronía del grupo y la notificación. Carga
   `hr_applicant_interviewer_rule` y la quita de las omisiones del XML.

## RED y anulaciones (esta unidad)

- Los tests exigen `interviewer_ids` en los dos modelos, la tabla
  `hr_job_res_users_rel` (`hr_job_id`, `res_users_id`) y
  `hr_applicant_res_users_interviewers_rel` (`hr_applicant_id`,
  `res_users_id`), y que una fila escrita antes de la migración siga después.
- Anulación: sin `relation` se recupera la tabla que nombra Django y caen
  exactamente los casos de tabla y columnas.

## Lo que esta unidad no cierra

- `hr-applicant-basemodel-0397`: el punto 2 de arriba.
- La escritura de `hr.job` que añade al grupo a sus entrevistadores
  (`hr_job.py:287-336`) sigue declarada BLOQUEADA en la cabecera de
  `hr_job.py`. Requiere `hr.job` sobre `BaseModel` (addon `hr`, grupo B).
  Sucesor: `recruitment-job-interviewer-sync-0397`.
