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

## Unidad A — skills

Medición exploratoria en un worktree aparte (`exp-hr-a`, base `fd0331d8`
más el commit de Many2many): las cinco clases cambian su base a
`(models.BaseModel, TimeStampedModel)`, la misma forma que
`HrIndividualSkillMixin`. Sobre `tests/unit/hr_skills`,
`tests/unit/hr_recruitment_skills`, `tests/unit/hr`,
`tests/unit/orm/test_translated_ordering.py` y `tests/integration/test_orm`
(el subconjunto derivado: los únicos directorios que nombran estos modelos):
**4 failed, 562 passed, 3 errors**. Dos causas:

1. `_compute_skill_id` y `_compute_skill_level_id` del mixin usaban la API
   de `QuerySet` (`.first()`, `.filter(default_level=True)`) sobre
   `skill_ids`/`skill_level_ids`. Con un comodelo `BaseModel` el valor es un
   recordset; la fuente (`hr_individual_skill_mixin.py:230-247`) usa
   `skill_ids[0] if skill_ids else False` y
   `skill_levels.filtered('default_level') or skill_levels[0] if skill_levels
   else False`. Se portan literales.
2. El fixture `two_types` de `test_translated_ordering.py` escribía
   traducciones sin entorno; `BaseModel.update_field_translations` aplica
   `check_access` y la escritura sin usuario se rechaza. La referencia
   escribe sus datos de prueba como superusuario (`TransactionCase.env`,
   `odoo/tests/common.py:1192`); el fixture pasa a hacerlo dentro de
   `Environment(None, SUPERUSER_ID, {})`, la forma del fixture `env` de
   `test_orm`.

Con las dos adaptaciones el subconjunto da **569 passed, 6 xfailed**. Sin
migración: la herencia de `BaseModel` es Python y no cambia columnas.

Prueba discriminante añadida en `test_individual_skill_recordset.py`: los
cinco modelos derivan de `BaseModel` y `skill_type.skill_ids` es un
recordset de `hr.skill`. Control: devolver las cinco bases a
`TimeStampedModel` hace caer 10 pruebas — las 6 nuevas y los 4 cómputos del
contrato (`test_individual_skill_contract.py`), que con la forma de la fuente
dependen del recordset —; sobreviven las 30 restantes de `hr_skills` y
`test_translated_ordering`.

*Métrica:* el subconjunto derivado por `grep` de los nombres de modelo,
clase y addon en `tests/`.
*Ciega a:* consumidores que lleguen a estos modelos por herencia o por
recorrido sin nombrarlos; por eso la unidad cierra con el gate completo.

Gate completo en el worktree cualificado (`exp-hr-a`, base `8f69391c`,
`THYROX_ROOT=/home/user/thyrox THYROX_CLONE_PREFIX=kaupamex-`,
`pytest -n 4 -q --reuse-db -p no:randomly`): **12 587 passed, 66 skipped,
6 xfailed, 0 failed, 5 errors** en 547 s; los 5 errores son los de
`test_multidb_isolation.py` que exigen la base desechable de `ci-multidb`.

## Seguridad del grupo A (verificación posterior al commit)

La referencia declara para los cinco modelos diez filas de ACL
(`odoo19c: addons/hr_skills/security/ir.model.access.csv`): CRUD completo
para `hr.group_hr_user` y, para `base.group_user`, lectura (más alta en
`hr.skill`, y CRUD en `hr.resume.line`). Las reglas de
`hr_skills_security.xml` tocan `hr.resume.line` (tres) y los informes;
ninguna toca `hr.skill`, `hr.skill.level` ni `hr.skill.type`.

Medido en la base QA (`orm_x2hokp_qa`): `ir.model.access` tiene **89** filas
y **ninguna** de un modelo `hr.*`; `ir.model.data` no tiene `hr.group_hr_user`
ni `hr.group_hr_manager` (sí `base.group_user`). Sólo `base` siembra su ACL
(`src/addons/base/security/ir_model_access.py`, cuyo docstring fija que cada
addon siembra la suya); los addons de HR nunca lo hicieron.

Consecuencia, separada por clase de prueba:

| Quién | Antes del grupo A | Después |
|---|---|---|
| superusuario (`env.su`) | sin control (modelo de Django) | sin control: `check_access` se salta con `su`, como la fuente |
| usuario ordinario por la API de recordset | sin control (modelo de Django) | **denegado** en los cinco: no hay fila que conceda |
| usuario ordinario sobre `hr.employee.skill`/`hr.job.skill`/`hr.applicant.skill` | ya denegado antes de este cambio (ya eran `BaseModel`) | igual |

El grupo A no introduce una elevación: el fixture de traducciones escribe
sus datos como superusuario, que es el entorno de la referencia para datos
de prueba (`TransactionCase.env`, `odoo/tests/common.py:1192`), y la
aserción que mide (el orden por idioma) se lee fuera de esa elevación. Lo que
sí destapa es que la capa de seguridad de HR (grupos de
`hr/security/hr_security.xml`, ACL de cada addon `hr*`, sus reglas) no está
portada. Por eso el grupo A queda **implementado y verificado para el
superusuario; la aceptación queda pendiente** de esa capa (H-API-1216).

`addons/hr_skills` no expone vistas ni rutas: hoy no hay consumidor HTTP
que un usuario ordinario alcance; el cambio de conducta queda en la API de
recordset.

## Unidad S — capa de seguridad de HR (diseño, H-API-1216)

Contrato de la referencia (odoo-tools `abe4040ec1`):

- `hr/security/hr_security.xml`: el privilegio `res_groups_privilege_employees`
  (`:4`), los grupos `group_hr_user` (`:10`) y `group_hr_manager` (`:18`), y
  las reglas de registro desde `:28` (multiempresa de empleado,
  departamento, puesto, tipos…).
- `hr/security/ir.model.access.csv`: 26 filas.
- 17 addons `hr*` con su propio `security/ir.model.access.csv`; para el
  grupo A, `hr_skills/security/ir.model.access.csv` (20 filas) y
  `hr_skills_security.xml` (reglas de `hr.resume.line` e informes).

Mecanismo del árbol (REUSE, sin uno nuevo): el de `base` y `sale`. Por addon,
un módulo `security/` con dos entradas sobre un solo cuerpo —`seed()` sobre los
modelos vivos, registrada en `tests/conftest.py`, y `seed_<addon>_*(apps,
alias)` sobre los históricos para la migración de datos— y la lista de filas
**derivada** del CSV con la regla de `derive_base_acl.py` (una fila entra si
su `model_id:id` es el de un modelo cargado; permisos verbatim). Precedentes:
`src/addons/base/security/ir_model_access.py`,
`src/addons/base/data/res_groups_data.py`, `addons/sale/security/ir_rules.py`.

Orden: (1) grupos y privilegio de `hr`; (2) ACL de `hr` y de `hr_skills`
derivadas; (3) reglas de `hr_skills_security.xml` sobre `hr.resume.line`;
(4) el resto de addons `hr*` por el mismo camino.

Pruebas: usuario de `base.group_user` lee `hr.skill.type` y no escribe;
usuario de `hr.group_hr_user` hace CRUD; un usuario sin grupo queda
denegado; la fila global sin permisos no concede nada. Control: retirar la
fila de `base.group_user` hace caer exactamente la prueba de lectura.

## Pendiente

- Corregir la cita en el hallazgo de docs (`#365` → `TASK-API-0397`): es
  edición del consumidor `kaupamex-docs`, no del store.
- Medir qué modelos de `addons/hr*` no derivan de `BaseModel` y qué API de
  recordset usan; agrupar la transición.
