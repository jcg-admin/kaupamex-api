# `hr.job` sobre `BaseModel`, con la escritura de `hr_recruitment`

Creado: 2026-11-14T11:24:52 (UTC). TASK-API-0397. Unidad
`recruitment-job-interviewer-sync-0397` (fila de plan ya registrada), que
amplía su alcance a la base de `hr.job`, su condición necesaria.

## Búsqueda previa

Adopción de `BaseModel` y `overrides=` sobre `create`/`write`: el
patrón de `hr-applicant-basemodel-0397` (`15efec47`), REUSE. Los helpers
de pk de entrevistadores de `hr_applicant.py` se reutilizan.

## Contrato (odoo-tools `abe4040ec1`, `odoo19c:`)

- `hr/models/hr_job.py:80-92`: `create` con
  `mail_create_nosubscribe`; `write` con `handle_history_divergence`
  sobre `description` cuando hay un solo registro.
- `hr_recruitment/models/hr_job.py:287-336`: `create` añade
  `interviewer_ids` al grupo; `write` desactiva las candidaturas al
  archivar el puesto, sincroniza el grupo cuando cambia `interviewer_ids`,
  pasa las candidaturas en curso del reclutador anterior al nuevo cuando
  cambia `user_id`, y reescribe los valores por defecto del alias.

## Medido aquí (`15efec47`)

- `HrJob` deriva de `MailThread, TimeStampedModel`. `hr` no declara
  `create`/`write`; `hr_recruitment` los declara BLOQUEADOS en la cabecera
  de su `hr_job.py`.
- `mail.alias.mixin` no está portado: `alias_defaults` y
  `_alias_get_creation_values` siguen BLOQUEADOS (cabecera de
  `hr_recruitment/models/hr_job.py`).
- `handle_history_divergence` (`html_editor`): se mide al implementar si
  el árbol lo tiene; si no, se declara en el cuerpo del método.

## Decisión

1. `HrJob`: `models.BaseModel` primero.
2. `create`/`write` de `hr` en la clase (`mail_create_nosubscribe` si
   `MailThread` lo lee; la divergencia de historial si existe el helper).
3. `create`/`write` de `hr_recruitment` por `overrides=`: grupo
   entrevistador, desactivar candidaturas al archivar, y el cambio de
   reclutador sobre las candidaturas en curso. La sincronía del alias se
   declara bloqueada en el cuerpo.
4. Consumidores de relaciones inversas, a forma de recordset; tests que
   escriben, bajo superusuario.

## RED y anulaciones

- `HrJob` es `BaseModel`.
- `job.write({'interviewer_ids': [Command.set([u])]})` añade `u` al grupo
  entrevistador; vaciarlo lo quita.
- Archivar el puesto (`active=False`) archiva sus candidaturas.
- Cambiar `user_id` pasa las candidaturas en curso del reclutador anterior
  al nuevo, y no las de otro reclutador.
- Anulación: sin el `overrides=` de `hr_recruitment` caen exactamente los
  tres casos de escritura.
