# Dependencias de HR sobre `BaseModel` y la cita durable de H-API-1083

Estado: medición de identidad; la transición de los modelos de HR se diseña
en la siguiente pasada de esta unidad.

## La cita `#365` no es durable

`H-API-1083` (`kaupamex-docs: …/completar-raiz-orm/hallazgos/
hallazgo-H-API-1083-…rst:16,95`) nombra su sucesor como «tarea **#365**».
Medido en el TaskStore de Thyrox, abierto en **solo lectura**
(`sqlite3 …?mode=ro`, sin escritura):

| `task_id` | sesión | cita durable | asunto |
|---|---|---|---|
| 365 | `168b0fdf…` | `TASK-API-0207` | Gate: identificadores en español en src/ y tests/ (H-API-607) |
| 1167 | `168b0fdf…` | **`TASK-API-0397`** | Construir BaseModel propio desde el contrato medido de la referencia |
| 1168 | `168b0fdf…` | `TASK-API-0398` | Verificar contrato por contrato los 21 del cubo TRAE de BaseModel |

El `#365` de H-API-1083 venía de la sesión `29a5e555…`, que no tiene fila
`365` en el store: el ordinal del board reinició por sesión y hoy resuelve a
otro sujeto. La TASK canónica de la obligación de H-API-1083 es
**TASK-API-0397** (y TASK-API-0398 para la verificación del cubo TRAE).

*Métrica:* filas de `tasks` por `task_id` y por asunto (`BaseModel`,
`1083`, `#365`).
*Ciega a:* una TASK cuyo asunto no nombre `BaseModel` y cubra la misma
obligación.

## Modelos de HR fuera de `BaseModel` (medido sobre `c9c7b545`)

Registro `orm.registry.MODELS_BY_NAME` con `config.settings.testing`:
**202** modelos registrados, **54** derivan de `BaseModel`. De los **28**
`hr.*`, sólo **3** derivan: `hr.applicant.skill`, `hr.employee.skill`,
`hr.job.skill`. Los 25 restantes, por grupo coherente (el grupo lo fija qué
modelos se referencian entre sí, no el addon):

| Grupo | Modelos | Por qué juntos |
|---|---|---|
| A — skills | `hr.skill`, `hr.skill.level`, `hr.skill.type`, `hr.resume.line`, `hr.resume.line.type` | los tres `*.skill` que ya son `BaseModel` los leen como comodelo; hoy el recordset termina en un `QuerySet` de Django |
| B — núcleo | `hr.employee`, `hr.employee.public`, `hr.version`, `hr.employee.category`, `hr.contract.type`, `hr.departure.reason`, `hr.work.location`, `hr.employee.location`, `hr.payroll.structure.type` | `hr.employee` y `hr.version` comparten campos por `_inherits`; las demás son sus comodelos |
| C — reclutamiento | `hr.applicant.category`, `hr.applicant.refuse.reason`, `hr.job.platform`, `hr.recruitment.degree`, `hr.recruitment.source`, `hr.recruitment.stage`, `hr.talent.pool` | comodelos de `hr.applicant` |
| D — work entry | `hr.work.entry`, `hr.work.entry.type`, `hr.user.work.entry.employee` | su propio addon |

Orden propuesto: A (el más pequeño y el que ya tiene consumidores
`BaseModel`), después B, C y D. Cada grupo cambia la base de sus clases,
regenera nada en la base de datos (la herencia de `BaseModel` es Python) y
se verifica con la suite de su addon más `test_orm`.

*Métrica:* `issubclass(model, BaseModel)` sobre el registro cargado.
*Ciega a:* qué API de recordset usa cada consumidor de esos modelos; eso se
mide por grupo antes de cambiar su base.

## Pendiente

- Corregir la cita en el hallazgo de docs (`#365` → `TASK-API-0397`): es
  edición del consumidor `kaupamex-docs`, no del store.
- Medir qué modelos de `addons/hr*` no derivan de `BaseModel` y qué API de
  recordset usan; agrupar la transición.
