# `hr.applicant` sobre `BaseModel`, con `create`/`write` de la fuente

Creado: 2026-11-14T10:31:58 (UTC). TASK-API-0397. Unidad `hr-applicant-basemodel-0397`,
sucesora de `recruitment-interviewer-fields-0397` (`b314f6e7`).

## Búsqueda previa

- Adopción de `BaseModel` y seguridad por manifiesto: el patrón de las
  unidades de utm, sales_team, resource, hr_work_entry y los comodelos de
  hr_recruitment (REUSE).
- Encadenar `create`/`write` de un addon que extiende sobre los de otro:
  `orm.method_chain.wrap_method` / `overrides=` de `extend_model`
  (REUSE; precedente `addons/account/models/digest.py:206`).

Veredicto: REUSE.

## Contrato (odoo-tools `abe4040ec1`, `odoo19c:`)

- `hr_recruitment/models/hr_applicant.py:617-645` `create`: fija
  `date_open` si hay `user_id`, recorta `email_from`, `super().create`,
  `interviewer_ids._create_recruitment_interviewers()` en sudo,
  `pool_applicant_id` para los que tienen `talent_pool_ids` y notifica a
  los entrevistadores.
- `:647-700` `write`: lee `old_interviewers` antes; `date_open`,
  `date_last_stage_update`, `kanban_state`, `last_stage_id` y el ajuste de
  `job_id.no_of_recruitment` cuando cambia la etapa; `super().write`;
  sincroniza el candidato del pool; con `'interviewer_ids' in vals` quita
  y añade al grupo y notifica a los nuevos.
- `hr_recruitment_skills/models/hr_applicant.py:147-166`: `create` y
  `write` que extienden los de arriba con `super()`.
- `hr_recruitment/security/hr_recruitment_security.xml:49-60`:
  `hr_applicant_interviewer_rule`.

## Medido aquí (`b314f6e7`)

- `HrApplicant` deriva de `MailThread, MailActivityMixin, UtmMixin,
  TimeStampedModel`. Su `save()` hace un subconjunto de `write`: fija
  `date_last_stage_update` en TODA edición (la fuente, sólo con
  `stage_id`/`kanban_state`) y la sincronía de entrevistadores, que no se
  dispara (sonda en `designs/recruitment-interviewer-fields.md`).
- `hr_recruitment_skills` instala `create` como `classmethod` nuevo
  («no hay previa que relevar») con `cls.objects.create`, y `write` con
  `setattr` + `save()`: los dos se saltan la cadena de la fuente. Con
  `BaseModel` sí hay previa, así que pasan a `overrides=` con `super`.
- `hr_recruitment_sms` sólo añade `action_send_sms`: no le afecta.
- Tests que escriben candidatos: `tests/unit/hr_recruitment_skills/`
  (`HrApplicant.objects.create` y `HrApplicant.create([...])`).

## Decisión

1. Bases: `models.BaseModel` primero.
2. `create`/`write` de `hr_recruitment` portados como en la fuente;
   `save()` deja de llevar esa lógica.
3. `create`/`write` de `hr_recruitment_skills` encadenados con
   `overrides=`, con el `super()` de la fuente.
4. La regla del entrevistador cargada y retirada de la lista de omisiones
   del XML.
5. Los tests que escriben lo hacen bajo superusuario.

## RED y anulaciones

- Entrevistador sin grupo de reclutamiento: ve los candidatos de un puesto
  donde entrevista y los que entrevista directamente, y no ve los demás.
- `write({'interviewer_ids': ...})` añade y quita del grupo entrevistador.
- `write` fija `date_last_stage_update` sólo con `stage_id` o
  `kanban_state`.
- Anulación A: base anterior → caen los casos de regla y de `write`.
- Anulación B: regla retirada del XML y su fila borrada → caen exactamente
  los casos de regla.

## Lo que esta unidad no cierra

- `recruitment-job-interviewer-sync-0397`: la escritura de `hr.job`.
- La notificación (`message_notify`) se porta con el contrato que ya tiene
  `MailThread` aquí; si su firma no admite los argumentos de la fuente,
  la divergencia se declara en el cuerpo del método.
