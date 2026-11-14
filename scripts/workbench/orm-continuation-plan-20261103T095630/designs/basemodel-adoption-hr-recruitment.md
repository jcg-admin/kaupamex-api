# `hr_recruitment`: comodelos sobre `BaseModel` y su seguridad (grupo C de HR)

Creado: 2026-11-14T09:39:01 (UTC). TASK-API-0397. Grupo C de `designs/hr-basemodel-dependencies.md`.

## Búsqueda previa

Mecanismo: seguridad por manifiesto (`designs/security-data-by-manifest.md`,
REUSE). Al medir el CSV apareció que `hr_recruitment.model_hr_job` no existía:
la raíz no reflejaba los modelos que un módulo extiende. Se corrigió antes,
en su propia unidad (`registry-load-extended-models-0485`, `b26523be`).

## Contrato (odoo-tools `abe4040ec1`)

`security/hr_recruitment_security.xml`: privilegio, 4 grupos, la ampliación de
`base.group_user` y 8 reglas. `ir.model.access.csv`: 31 filas.

## Medido aquí (`fa148ec1`)

- CSV: 12 filas sin destino. `calendar` no está portado (2); los cuatro
  asistentes son `TransientModel` abstractos (8); `mail.activity.plan` y su
  plantilla no existen (2).
- XML: `mail.message` no tiene `_name` ni XML-ID (`mail_message_user_rule`);
  `mail.activity.plan[_template]` no existen (dos reglas); `base.user_admin`
  no existe.
- `hr_applicant_interviewer_rule` no resuelve: `to_q` rechaza
  `interviewer_ids` en `hr.applicant` (aquí `interviewers`, forma A) y en
  `hr.job` (el campo de `hr_recruitment` no está portado como campo).

## Decisión

1. Los siete comodelos de `hr.applicant` —categoría, motivo de rechazo,
   plataforma, grado, fuente, etapa y bolsa de talento— derivan de `BaseModel`.
2. La seguridad, copia fiel, por manifiesto, con las omisiones medidas
   declaradas en la cabecera del XML y en el manifiesto.
3. Sucesora `recruitment-interviewer-fields-0397`: `hr.job.interviewer_ids`
   como campo, `interviewers` → `interviewer_ids` (forma C), `hr.applicant`
   sobre `BaseModel` y la regla del entrevistador cargada.

## Pruebas

Los siete son `BaseModel`; los grupos se implican como en la fuente; 19 filas
y 4 reglas con XML-ID; un oficial de reclutamiento crea etapas; un usuario
interno las lee y no las escribe. Anulaciones: bases y manifiesto.
