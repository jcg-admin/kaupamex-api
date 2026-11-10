# U5 — transformadores de comandos de `hr.individual.skill.mixin`

Referencia: odoo-tools `abe4040ec1`,
`odoo19c: addons/hr_skills/models/hr_individual_skill_mixin.py:257-537`,
consumidores `hr_employee.py:45-57` y `hr_job.py:55-66`. Diseño padre:
`hr-individual-skill-mixin-full-port.md`.

## Flujo de la referencia

`hr.employee.create/write` y `hr.job.create/write` juntan los comandos de
`current_*_skill_ids`, `certification_ids` y `*_skill_ids`, y los reemplazan
por `env[modelo]._get_transformed_commands(comandos, self)` antes de
`super()`. El transformador:

1. `_get_transformed_commands(commands, individuals)` (`:481-537`): reparte
   `1` (escribir), `2` (borrar), `0` (crear; en `create` del individuo copia
   el comando por cada individuo y fija el campo ligado); si un id aparece en
   `1` y `2`, el `1` se descarta; devuelve
   `_expire_individual_skills(borrados) + _write_individual_skills(escritos) +
   _create_individual_skills(creados)`.
   *Defecto de la fuente:* la rama de ids mixtos hace `updated_ids = set()` y
   luego `updated_ids.append(...)` — `AttributeError` si se alcanza. Se porta
   la intención (conservar los `1` no mixtos) y se declara la divergencia con
   su prueba; portar el `AttributeError` no es fidelidad sino reproducir un
   fallo.
2. `_expire_individual_skills()` (`:257-294`): borra (`2`) lo creado desde
   ayer o ya vencido; archiva (`1`, `valid_to = ayer`) lo demás, salvo que
   archivarlo choque con otro registro (`_get_overlapping_individual_skill`
   con `valid_to = ayer`), en cuyo caso lo borra.
3. `_create_individual_skills(vals_list)` (`:296-415`): busca en una sola
   consulta las habilidades vigentes de cada `(individuo, skill)`; quita
   duplicados del lote por `(individuo, skill, desde, hasta)`; una
   certificación idéntica existente se omite; una habilidad regular existente
   se archiva; devuelve `expire(archivadas) + [[0, 0, vals] …]`.
4. `_write_individual_skills(commands)` (`:417-479`): si el `write` no toca
   `skill_type_id`, `skill_id`, `skill_level_id` ni el campo ligado, pasa
   igual; si los toca, archiva el registro y crea uno nuevo con los valores del
   registro, los `vals` y los campos pasivos (`_get_passive_fields`); las
   fechas se conservan sólo para certificaciones.

## Estado y capacidades (TRAE / CONSTRUYE)

| Capacidad | Estado |
|---|---|
| `Domain`, `search`, `grouped`, `filtered`, `browse`, `ids` en `hr.*.skill` | TRAE — recordsets desde U1 |
| `_get_overlapping_individual_skill` | TRAE — U3 |
| comandos `0`/`1`/`2` sobre un `One2many` en `write` | TRAE — `RecordLoaderMixin._pop_one2many_values` + `apply_one2many_commands` |
| `super()` en una extensión de `hr.employee`/`hr.job` | TRAE — `orm.method_chain.wrap_method` |
| `hr.employee.create` con comandos | TRAE — `DefaultGetMixin.create` |
| `hr.job.create` / `hr.applicant.create` con comandos | DEPENDENCIA INSATISFECHA — no adoptan el `create` del ORM (H-API-1083); `write` sí |
| los cuatro transformadores | CONSTRUYE — porte |
| `current_*_skill_ids`, `certification_ids` como campos escribibles | DEPENDENCIA — hoy son propiedades de sólo lectura; sólo `*_skill_ids` llega como campo |

## Pruebas (RED primero)

- `_expire_individual_skills`: creado hoy → `[2, id]`; antiguo y vigente →
  `[1, id, {'valid_to': ayer}]`; antiguo cuyo archivo chocaría → `[2, id]`.
- `_create_individual_skills`: nueva habilidad con una regular vigente →
  archivo de la vieja + creación; duplicado en el lote → una sola creación;
  certificación idéntica existente → omitida.
- `_write_individual_skills`: cambio de nivel → archivo + creación con los
  valores; cambio de otro campo → `[1, id, vals]` intacto.
- `_get_transformed_commands`: mezcla de `0`/`1`/`2`; id en `1` y `2`.
- Integración: `job.write({'job_skill_ids': [[0, 0, {...}]]})` sobre un
  puesto con la misma habilidad vigente archiva la anterior y crea la nueva
  (ruta real de `RecordLoaderMixin.write`).

## Resultado y expectativas corregidas

13 pruebas en verde. Dos expectativas del RED no reproducían la fuente; se
corrigieron con este registro:

| | Expectativa previa | Evidencia | Expectativa corregida | Resultado | Control que discrimina |
|---|---|---|---|---|---|
| 1 | `hr.job.skill` omite una certificación idéntica | `hr_job_skill.py:23-24`: `_can_edit_certification_validity_period` devuelve `False`, así que la certificación se trata como regular (`:390-395`) | en `hr.job.skill` la vigente se archiva y se crea la nueva; la omisión se prueba en `hr.employee.skill` | verde las dos | la prueba del puesto falla si se ignora el override; la del empleado, si se retira la rama `certification_set` |
| 2 | un `write` de campo base devuelve archivo + creación | `:479` suma `expire(self - …)` y `_create_individual_skills(create_vals)`, que vuelve a encontrar vigente el registro escrito | el archivo sale dos veces, con el mismo `valid_to` | verde | la prueba falla si se deduplica el archivo |

Hallazgo de ORM destapado: `_pop_one2many_values` excluía por
`type != 'one2many'`, y `ForeignObjectRel.type` también vale `'one2many'`;
la relación inversa de Django se excluía a sí misma y un `write` con comandos
moría con *Direct assignment to the reverse side*. Se discrimina por clase
(`DeclaredOne2many`).

Controles de anulación (cada uno tumba exactamente sus pruebas):

| Retirado | Caen |
|---|---|
| discriminador por clase → por `type` | `writing_a_job…`, `writing_an_employee…` |
| `overrides` de `hr.job` | `writing_a_job…` |
| `overrides` de `hr.employee` | `writing_an_employee…`, `creating_an_employee…` |
| `set.add` en la rama mixta | `transformed_commands_drop…` |

`hr.job.create` sigue como dependencia insatisfecha (H-API-1083).

## Gate

Suite completa sobre el worktree (`gate-u5-20261110T064702.log`):
12 549 passed, 66 skipped, 4 xfailed, 2 failed, 5 errors. Atribución:

- 5 errores de `test_multidb_isolation.py`: ambientales; exigen base
  desechable, y `make ci-multidb` pasa 5/5 sobre `eed440d4`.
- 2 fallos de `test_check_workbench.py`: del emplazamiento. El guion busca
  thyrox como hermano del repo y el worktree vivía en el scratchpad; el mismo
  archivo de test, que este cambio no toca, da 20/20 en el árbol principal.

Tras el gate se partieron cinco líneas largas que la admisión rechazaba. El
AST de los tres archivos afectados es idéntico al del árbol que pasó el gate
(`ast.dump` comparado); `tests/unit/hr_skills` da 30 passed sobre la
versión commiteada.
