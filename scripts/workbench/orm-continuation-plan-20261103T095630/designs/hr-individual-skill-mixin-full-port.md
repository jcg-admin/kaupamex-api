# Porte completo de `hr.individual.skill.mixin` y sus flujos

Fecha: 2026-11-10T04:28:30Z. Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`,
`odoo19c: addons/hr_skills/models/hr_individual_skill_mixin.py` (537 líneas).
Origen: directiva del ejecutor 2026-11-10 — documentar cómo lo hace la
referencia y portarlo **completo**; la referencia no usa `TimeStampedModel`
como base del mixin.

## Cómo lo hace la referencia

`class HrIndividualSkillMixin(models.AbstractModel)` — un `BaseModel`
abstracto: todo consumidor es un **recordset** con `env`, `search`,
`Domain`, `@api.constrains`, `@api.depends`, `@api.onchange` y comandos
x2many. Sus consumidores: `hr.employee.skill`, `hr.job.skill`
(`hr_skills`) y `hr.applicant.skill` (`hr_recruitment_skills`).

Flujos:

1. **Alta/edición por comandos del padre.** `hr.employee`/`hr.job`
   reescriben `create`/`write`: los comandos sobre su One2many de
   habilidades pasan por `_get_transformed_commands` (`:481-537`), que
   reparte en `_create_individual_skills` (`:296-416`, archiva la versión
   anterior de la misma habilidad en vez de duplicarla) y
   `_write_individual_skills` (`:417-480`, una escritura de campo activo
   crea una versión nueva y archiva la vieja); las bajas pasan por
   `_expire_individual_skills` (`:257-295`, borra lo creado ayer o
   caducado, archiva con `valid_to = ayer` el resto, y borra lo que al
   archivar chocaría).
2. **Restricción de solape por lote.** `_check_not_overlapping_regular_skill`
   (`:64-110`) construye un `vals` por registro y llama
   `_get_overlapping_individual_skill` (`:111-195`): un único `search` con
   el `Domain.OR` de todos los candidatos, y el emparejamiento en memoria
   por `(vinculado, skill)` o `(vinculado, skill, nivel, desde, hasta)`.
3. **Defaults y cómputos.** `skill_type_id` toma `_default_skill_type_id`
   (`:42-45`, con `certificate_skill` en el contexto busca un tipo
   certificación); `skill_id`/`skill_level_id` se calculan almacenados y
   editables; `level_progress`, `color`, `levels_count`, `is_certification`
   son `related`; `certification_skill_type_count` es `compute`;
   `display_name` es `"<skill>: <nivel>"` (`:249-253`).
4. **Onchanges.** `_onchange_is_certification`, `_onchange_valid_date`.

## Cómo está aquí (medido)

- Base `TimeStampedModel` (fila de Django): sin `env`, `search`, comandos.
- 5 campos `related`/`compute` portados como **propiedades**.
- `_default_skill_type_id` → función de módulo `_default_skill_type` sin
  rama `certificate_skill` (DIVERGENCIA 1).
- `_check_not_overlapping_regular_skill` por instancia (DIVERGENCIA 2);
  `_get_overlapping_individual_skill` BLOQUEADO.
- `_compute_display_name` → `__str__`.
- 4 métodos de comandos BLOQUEADOS por *«el protocolo de comandos x2many no
  existe en este ORM»* (DIVERGENCIA 3).
- Consumidores: `HrEmployeeSkill`, `HrJobSkill`, `HrApplicantSkill`, los
  tres filas de Django.

## Premisas caducadas (medidas hoy)

| Bloqueo citado | Hoy |
|---|---|
| `fields.Domain` no exportado (`hr_job.py:28`, `hr_employee.py:46`) | exportado por la fachada `fields` (TASK-API-0345 cumple su premisa) |
| protocolo de comandos x2many inexistente (DIVERGENCIA 3) | existe para `BaseModel` (`Command`, aplicación de comandos, `_check_sudo_commands`) |
| `copy()` genérico inexistente (`hr_skill_type.py:41`) | `CopyMixin` y `BaseModel.copy` |
| `@api.onchange` sin motor (`hr_skill_type.py:38`, mixin) | `api.onchange` y `BaseModel._apply_onchange_methods` |
| `@api.depends_context` (`hr_skill.py:20`) | `api.depends_context` existe |
| `convert.convert_file` (`hr_employee.py:51`) | `tools.convert.convert_file` existe |

La causa común no es el ORM: es que los modelos de `hr_skills` son filas de
Django. La decisión que lo resuelve ya está registrada: **H-API-1083**, los
modelos portados derivan de `BaseModel`. Precedente de producción:
`base.IrAttachment` (`1da88953`): `BaseModel` sin cambio de columnas, ACL
del modelo sembrada por migración, pruebas con el entorno de superusuario.
Forma en el árbol: `TestOrmModel(BaseModel, TimeStampedModel)` con
`class Meta(TimeStampedModel.Meta)` para que el esquema migrado no cambie.

`orm.models.AbstractModel` es el registrante **sin tabla** (no es base de
un mixin con campos); el mixin de la fuente se porta como `BaseModel`
abstracto de Django.

## Plan de porte (unidades, en orden de dependencia)

| U | Contenido | Prueba que lo discrimina |
|---|---|---|
| U1 | mixin `BaseModel` abstracto; los 3 consumidores recordsets; ACL; sin cambio de columnas | `env['hr.employee.skill'].search`/`create`; guarda de sincronía de migraciones |
| U2 | `_default_skill_type_id` con `certificate_skill`, como default del campo | default con y sin contexto |
| U3 | `_get_overlapping_individual_skill` + restricción por lote con `Domain` | dos altas que chocan entre sí en un mismo `create` |
| U4 | campos `related`/`compute` y `_compute_display_name` | `read`/`display_name` |
| U5 | `_expire/_create/_write_individual_skills`, `_get_transformed_commands` y los `create`/`write` de `hr.employee`/`hr.job` | versión archivada en vez de duplicada; baja que archiva |
| U6 | lo de `hr_skill_type`, `hr_job` (`_search_current_job_skill_ids`) y `hr_employee` (`_add_certification_activity_to_employees`, TASK-API-0345) | por método |

## Identidad de tarea

TASK-API-0345 (`pending`) cubre la parte que dependía de `Domain` en
`hr_skills`. El resto no tiene TASK canónica en el store, y acuñarla
escribe en el store de Thyrox, prohibido desde este nodo (directiva del
ejecutor 2026-11-10). Las unidades se citan por este diseño hasta que VM-A
acuñe su identidad; no se inventa ninguna.

## U1 — resultado (2026-11-10)

- RED: 4/4 (`issubclass(..., BaseModel)` falso; `HrJobSkill` sin `search`).
- Cambio: `HrIndividualSkillMixin(models.BaseModel, TimeStampedModel)` con
  `Meta(TimeStampedModel.Meta)`; la guarda de sincronía de migraciones
  sigue verde (sin cambio de columnas).
- Dos huecos del ORM destapados por el primer `search` y corregidos donde
  viven:
  1. `_order_field_to_sql` sobre un `Many2one` cuyo comodelo es fila de
     Django (`_from_ids` inexistente): se delega en una fila sin guardar del
     comodelo, que trae `_order_to_sql` por `OrderMixin`.
  2. `_many2one_condition_to_sql` comparaba `field_expr` sólo con el nombre;
     el dominio de la fuente dice `skill_id` y el campo aquí es `skill` con
     columna `skill_id`: se acepta también `attname`.
- GREEN: 5 passed. Anulación (restaurada con `cmp`): base vieja → 4 caen;
  sin la delegación al comodelo → caen las 2 búsquedas (las dos ordenan por
  `_order`); sin `attname` → cae sólo la del camino `skill_id.name`.
- Regresión derivada (`tests/unit/{orm,hr,hr_recruitment_skills,hr_skills}`,
  `tests/integration/{test_orm,base}`): 4170 passed, 0 failed.
- ACL: la referencia declara filas para `hr.employee.skill`/`hr.job.skill`
  con `hr.group_hr_user` y `base.group_user`; los grupos de `hr` no están
  sembrados y el sembrador de ACL sólo resuelve grupos de `base`
  (`_group_by_xmlid`). Sin ACL, un usuario que no sea superusuario no lee
  estos recordsets; hoy ningún consumidor lo hace. Dependencia registrada:
  datos de grupos de `hr` y sembrado de ACL por addon.
