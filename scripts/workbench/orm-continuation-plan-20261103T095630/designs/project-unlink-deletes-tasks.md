# `project.project.unlink` borra las tareas; la FK de la tarea es `set null`

Unidad: `orm-fk-delete-policy-contract-0515` (TASK-API-0515), fila
`project.ProjectTask.project`, apartada del bloque D. Escrito el
2026-11-18, antes de tocar `addons/project/models/`.

## Contrato de la referencia (medido)

| Símbolo | Cita | Contrato |
|---|---|---|
| `project.task.project_id` | `odoo19c: addons/project/models/project_task.py:192-193` | `Many2one('project.project')`, no obligatorio, sin `ondelete`: `set null` |
| `project.project.tasks` | `odoo19c: addons/project/models/project_project.py:107` | `One2many('project.task', 'project_id')` |
| `project.project.unlink` | `odoo19c: addons/project/models/project_project.py:704-716` | (1) borra las configuraciones de acciones embebidas del proyecto (`res.users.settings.embedded.action` con `res_model` y `res_id`); (2) aparta las cuentas analíticas sin líneas; (3) `self.with_context(active_test=False).tasks.unlink()`; (4) `super().unlink()`; (5) borra las cuentas apartadas |
| `project.task.unlink` | `odoo19c: addons/project/models/project_task.py:1388-1395` | añade las subtareas y borra la recurrencia cuya última tarea es ésta |
| atributos de clase | `odoo19c: addons/project/models/project_project.py:24-36` | `_name`, `_description`, `_inherit` (6 mixins), `_order`, `_rating_satisfaction_days`, `_track_duration_field` |

Las tareas no desaparecen por la base (la FK las dejaría con el proyecto
vacío): las borra el `unlink` del proyecto, incluidas las archivadas.

## Nuestro estado (medido en `6ec1e3df`)

- `Project`, `ProjectTask` y `ProjectTaskType` son `TimeStampedModel` sin
  `BaseModel`, sin `_name` y sin `unlink` (212 líneas entre los tres
  archivos). `ProjectTask.project` es `CASCADE`.
- La prosa heredada de `project_project.py` dice que la analítica «no existe
  en este stack (Clausula 5)». Clasificación: **OUTDATED** —
  `account.analytic.account` existe
  (`addons/analytic/models/analytic_account.py:43`)—; lo que falta es el
  campo `account_id` del proyecto.
- `res.users.settings.embedded.action` existe como modelo de Django
  (`addons/web/models/res_users_settings_embedded_action.py:72`).
- Consumidores: 11 altas con `objects.create` en `tests` y `addons`; nueve
  módulos extienden o leen `Project`/`ProjectTask` (`sale_timesheet`,
  `hr_timesheet`, `project_sms`, `project_todo`, `project_stock`,
  `project_account`).

## Cambio

1. `Project(models.BaseModel, TimeStampedModel)` con `_name`,
   `_description` y `_order` de la fuente. `_inherit`,
   `_rating_satisfaction_days` y `_track_duration_field` se declaran como
   en la fuente; la herencia efectiva de los seis mixins no entra aquí y
   queda como sucesor (mismo criterio que
   `designs/account-journal-inherited-prose.md`).
2. `ProjectTask(models.BaseModel, TimeStampedModel)` con `_name` y
   `_description`: sin él, `tasks.unlink()` no existe.
3. `Project.unlink`, con los cinco pasos. Los pasos 2 y 5 quedan
   `pendiente: account_id` en el archivo, porque el proyecto no declara ese
   campo; no se omiten en silencio.
4. `ProjectTask.project`: `on_delete=models.SET_NULL`. Migración
   `0009_set_null_task_project` de `project`.
5. `project.task.unlink` (subtareas y recurrencia): `parent_id` y
   `recurrence_id` no existen en nuestra tarea; queda declarado como
   sucesor, no portado a medias.

## Pruebas

`tests/unit/project/test_project_unlink_deletes_tasks.py`:

| Caso | Espera |
|---|---|
| `project.unlink()` con una tarea activa y una archivada | las dos desaparecen con el proyecto |
| `project.unlink()` con una configuración de acción embebida del proyecto | la configuración desaparece; la de otro proyecto sigue |
| borrado de la fila del proyecto sin pasar por `unlink` | la tarea sigue, con `project` nulo (la política de la FK) |

Y la fila del contrato en `tests/unit/orm/test_delete_policy_contract.py`.

Anulaciones: retirar el paso 3 deja las tareas con el proyecto vacío (cae
el primer caso); retirar el paso 1 cae el segundo; devolver la FK a
`CASCADE` cae el tercero y la fila del contrato.

*Métrica:* filas de `project_task` y de la configuración leídas de la base.
*Ciega a:* subtareas y recurrencia, que no existen aquí; y a quien borre un
proyecto con `QuerySet.delete()`, que deja las tareas huérfanas donde antes
las borraba. Los sitios que lo hacen se miden al implementar.
