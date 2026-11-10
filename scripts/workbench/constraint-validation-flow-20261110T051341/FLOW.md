# Validación de restricciones Python en `create` y `write` — flujo de referencia y estado

Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`,
`odoo19c: odoo/orm/models.py` salvo indicación. Árbol medido: kaupamex-api
`28e8c8c5` + diff de trabajo (hashes abajo). Fecha: 2026-11-10 (`date -u`).

Este documento sustituye a la primera versión del diseño
(`designs/validate-stored-constraints.md`), que nombraba sólo la llamada a
`_validate_fields` y no el resto del flujo, ni el arnés de pruebas del que la
afirmación de atomicidad dependía. Esa versión se queda como evidencia de lo
que se supuso.

## 1. Flujo de la referencia, paso a paso

### 1.1 Selección de métodos — `_constraint_methods` (`:519-546`)

1. `getmembers(cls, is_constraint)`: todos los atributos invocables con
   `_constrains`, **heredados incluidos**, en orden **alfabético** de nombre.
2. Un `_constrains` invocable se resuelve con `self.sudo()` y se envuelve en
   un proxy con los nombres fijos; el original no se toca.
3. Por cada nombre: aviso si no es campo; aviso si no es `store`, `inverse`
   ni `inherited`.
4. Memoizado en la clase.

### 1.2 Despacho — `_validate_fields` (`:1253-1268`)

1. Lista vacía → retorno.
2. `records = self.sudo()` — corre elevado, como un calculado almacenado.
3. Un método corre si **alguno** de sus nombres está en `field_names` y
   **ninguno** en `excluded_names`. El método recibe el recordset entero
   (`check(records)`): una restricción de lote ve todas las filas.
4. Los nombres son únicos por campo en la fuente.

### 1.3 `create` (`:4611-4752`)

1. `vals_list` vacío → `browse()`.
2. `check_access('create')`.
3. Acceso de escritura a cada campo de los `vals` y de cada `default_*` del
   contexto; nombre desconocido → `ValueError`.
4. `_prepare_create_values` (defaults, `__precomputed__`).
5. Clasificación por registro: `stored`, `inversed` (inverso no
   precalculado), `inherited`, `protected` (calculados editables o
   precalculados); `bypass_search_access` comprueba lectura del comodelo.
6. Padres de `_inherits`: escritura o creación.
7. `records = self._create(data_list)` (§1.4).
8. Bajo `env.protecting(protected)`: inversos por grupo, con
   `_update_cache` de los valores no almacenados e
   `invalidate_recordset` de los x2many no almacenados.
9. **`data['record']._validate_fields(data['inversed'], data['stored'])`**
   por registro (`:4741`): los inversos no almacenados, excluyendo lo
   almacenado.
10. `_check_company_auto` → `records._check_company()`.
11. Importación: `_update_xmlids`.

### 1.4 `_create` (`:4849-4952`)

1. `INSERT … RETURNING id` por lotes de `INSERT_BATCH_SIZE`; los campos sin
   columna van a `other_fields`; `properties` siempre a `other_fields`.
2. Caché: `None` para lo no insertado, `()` para x2many, el valor
   convertido para lo insertado; inversos de `many2one`.
3. `_parent_store_create`.
4. Bajo `env.protecting`: `records.modified(self._fields, create=True)`;
   `field.create` de `other_fields` con contexto limpio de `default_*`;
   `modified` de esos campos.
5. **`records._validate_fields(name for data in data_list for name in
   data['stored'])`** (`:4948-4949`): una sola llamada para el lote.
6. `records.check_access('create')` (`:4950`) — después de validar.

### 1.5 `write` (`:4334-4518`)

1. Vacío → `True`; `check_access('write')`; acceso de campo; `ValueError`.
2. Contexto de importación, `write_date`/`write_uid` con `_log_access`.
3. Clasificación en `determine_inverses`; `protected`.
4. Bajo `env.protecting(protected, self)`: `modified(before=True)` de los
   relacionales, `real_recs = self.filtered('id')`, `field.write` por
   `write_sequence`, `self.modified(vals)`, `flush_model` del padre si cambia
   `_parent_name`.
5. **`real_recs._validate_fields(vals, inverse_fields)`** (`:4491`) — sólo
   registros con id; excluye los inversos.
6. Inversos (reescritura de no almacenados invalidados, `determine_inverse`,
   reenvolver `AccessError` de heredado).
7. **`real_recs._validate_fields(inverse_fields)`** (`:4514`).
8. `_check_company_auto` → `self._check_company(list(vals))`.

### 1.6 Recómputo — `_compute_field_value` (`:4954-4959`)

Calculado almacenado con filas reales → `_validate_fields` de
`field_computed[field]`. (Ya portado, H-API-1165.)

### 1.7 Transacción

Ni `create` ni `write` abren savepoint: una `ValidationError` deja las filas
insertadas en la transacción en curso y la deshace quien la envuelve (la
petición RPC). El arnés de pruebas de la fuente lo hace explícito:
`BaseCase._assertRaises` (`odoo19c: odoo/tests/common.py:502-517`) entra en
`self.env.cr.savepoint()` y lo deshace al saltar la excepción esperada;
`test_15_constraint` comprueba además `assertFalse(env.fields_to_compute())`
tras el `assertRaises`.

## 2. Estado de este árbol (medido)

| Paso | Estado | Clasificación |
|---|---|---|
| 1.1 selección | `_ConstraintMethods` (`registry.py:941-1037`), `dir()` alfabético, proxy del invocable, dos avisos | TRAE (ya portado) |
| 1.2 despacho, elevación, filtros | `_validate_fields` (`models.py:5551`) | TRAE |
| 1.2.4 nombre único | un `Many2one` tiene dos nombres (`skill`, `skill_id`) en `model_field_registry`; la comparación literal los separaba | CONSTRUYE — comparación por campo (diff de trabajo) |
| 1.3.9 inversos en `create` | `models.py:1017` | TRAE |
| 1.4.5 almacenados en `_create` | ausente antes del cambio | CONSTRUYE — diff de trabajo |
| 1.4.6 `check_access('create')` tras validar | ausente en `_create`; `create` lo comprueba al entrar | pendiente, dependencia de TASK-API-0510 (flujo de escritura) |
| 1.5.5 / 1.5.7 en `write` | ausentes antes del cambio | CONSTRUYE parcial — una validación de lo escrito tras escribir; el orden «no inversos, inversos, inversos» no está separado (pendiente con `_write`, TASK-API-0510) |
| 1.5.4 `real_recs` | `BaseModel.write` recorre registros guardados; un registro de `new()` no pasa por aquí | divergencia sin efecto observado, sin prueba |
| 1.7 savepoint en pruebas | `odoo/tests/` **no está porteado**; existe sólo el fixture `assert_raises` (`tests/integration/test_orm/conftest.py`), que imita `_assertRaises` con `transaction.atomic()` e invalida la caché | TRAE parcial; las pruebas de hr_skills usaron `transaction.atomic()` suelto sin reutilizarlo — corregido abajo |

### 2.1 Cobertura real — corrección de una cifra

La cifra «96 decoradores en 52 archivos» comunicada antes era falsa: el grep
contaba menciones en docstrings y comentarios (89 líneas). El censo por AST
(`probes/constraint_decorators.py` → `outputs/constraint-decorators.tsv`) da
**10 decoradores en 5 archivos**, que sobre modelos concretos son **18 pares
(modelo, método)** (`probes/constraint_matrix.py` →
`outputs/constraint-matrix.tsv`):

| Grupo | Pares | Antes | Después |
|---|---|---|---|
| `BaseModel` sin calculado almacenado (hr_skills ×3 modelos, `test_orm.message._check_author`) | 13 | nunca | `create`, `write` |
| `BaseModel` con calculado almacenado (`test_orm.message._check_name`) | 1 | recómputo | recómputo, `create`, `write` |
| Django con `RecordLoaderMixin.write` (`crm.lead._check_won_validity`) | 1 | recómputo | recómputo, `write` |
| Django sin el `create`/`write` del ORM (`account.move._check_balanced`, `res.users.settings.embedded.action` ×2) | 3 | nunca por despacho; los llaman `post` y `clean` explícitamente | sin cambio — pendiente con la adopción de `BaseModel` (H-API-1083) |

Tras U4b (`skill`/`skill_level` calculados almacenados) la matriz cambia:
las restricciones de hr_skills que nombran esos campos corren también por
recómputo. `outputs/constraint-matrix-pre-u4b.tsv` es la de arriba;
`outputs/constraint-matrix.tsv`, la del árbol del gate 3.

*Métrica:* métodos con `_constrains` recogidos por `registry.constraint_methods`
sobre `apps.get_models()`. *Ciega a:* una restricción en un modelo que no esté
registrado en Django, y a un `@constrains` aplicado por llamada en vez de por
decorador.

## 3. Resultado del gate sobre el cambio

Código probado (hashes al lanzar, 05:01:02Z; ningún archivo de código cambió
durante la ejecución):

```
f41c33ac…63b  src/orm/models.py
ab7ba672…9b0  addons/hr_skills/models/hr_individual_skill_mixin.py
```

`uv run pytest -n 4 -q --reuse-db -p no:randomly`:
**2 failed, 12508 passed, 66 skipped, 4 xfailed, 24 errors** (512 s).

- 5 errores `test_multidb_isolation`: defecto ambiental conocido.
- 2 fallos + 19 errores, **todos** `TypeError: argument of type
  'ManyRelatedManager' is not iterable` en
  `test_orm.py:724 _check_author` (re-ejecutados aparte: 21 de 21). La
  restricción es porte verbatim (`odoo19c: odoo/addons/test_orm/models/
  test_orm.py:177-180`) y antes nunca corría. **No son datos de prueba
  inválidos**: es un defecto latente del ORM (§4).

## 4. Dependencias destapadas

1. **Lectura de un `Many2many` de un `BaseModel` hacia un comodelo Django**
   devuelve el `ManyRelatedManager`, no el conjunto de filas del comodelo
   (`_x2many_descriptor_get`, `models.py:5783`, sólo convierte cuando ambos
   lados son `BaseModel`). Censo: un solo campo declarado afectado,
   `test_orm.discussion.participants` → `res.users`; los otros tres casos son
   accesores inversos automáticos de Django en `ir.attachment`, sin campo de
   la fuente. En la fuente el valor es un recordset del comodelo
   (`_RelationalMulti.convert_to_record`, `odoo19c: odoo/orm/fields_relational.py:643`).
2. **Álgebra de recordset para filas Django.** `test_15_constraint` escribe
   `discussion.participants -= self.env.user` y `+=`. El conjunto de filas de
   un modelo Django es `AccessQuerySet` (`models.py:318`); no tiene `+`, `-`,
   `&` ni `|` con una fila suelta como singleton (fuente `:6544-6610`).
3. `test_15_constraint_inverse` necesita `test_orm.compute.inverse`
   (`odoo19c: …/test_orm/models/test_orm.py:540-585`), no porteado.

## 5. Implementado (árbol del gate 2, 05:45:05Z, hashes en `outputs/gate2-hashes.txt`)

| Pieza | Dónde | Clasificación | Referencia |
|---|---|---|---|
| validación de almacenados en `_create` | `models.py`, `DefaultGetMixin._create` | CONSTRUYE | `:4948-4949` |
| validación en `write` (`BaseModel` una vez por recordset; fila Django en `RecordLoaderMixin.write`) | `models.py` | CONSTRUYE parcial (§2) | `:4491`, `:4514` |
| comparación por campo en `_validate_fields` | `models.py` | CONSTRUYE | `:1253-1268` |
| `Many2many` directo de `BaseModel` hacia Django → `AccessQuerySet` en `Meta.ordering` | `models.py`, `_x2many_descriptor_get` | CONSTRUYE | `fields_relational.py:643` |
| `AccessQuerySet.__add__/__sub__`, `&`/`|` con fila suelta; `&`/`|` entre `QuerySet` = los de Django | `models.py:AccessQuerySet` | CONSTRUYE (`&`,`|` entre QuerySet: TRAE) | `models.py:6544-6610` |
| asignar un `QuerySet` a un `Many2many` → `[Command.set(ids)]` | `RecordLoaderMixin._pop_many2many_values` | CONSTRUYE | `fields_relational.py:676-702` |
| `_FlushingSavepoint` y `savepoint(flush=True)` | `src/service/db.py` (porte de `sql_db`) | CONSTRUYE sobre `Transaction.flush` (TRAE); el `clear` del retorno es el corte `savepoint_rollback` ya portado (TRAE, `environments.py:_CURSOR_CUTS`) | `sql_db.py:132-151`, `:217-226` |
| `load` abre savepoints con vaciado | `models.py:3753`, `:3802` | divergencia cerrada | `models.py:921`, `:971` |
| `assert_raises` compartido = `_assertRaises` | `tests/conftest.py` (movido desde `test_orm/conftest.py`) | CONSTRUYE | `tests/common.py:502-524` |
| `Many2one` calculado y almacenado lleva `StoredMany2oneIdDescriptor` | `fields.py:_install_field_descriptor` | divergencia cerrada | `fields.py:1807-1841` |
| lectura de `Many2one`: caché del ORM antes que `__dict__` | `fields.py:StoredMany2oneIdDescriptor.__get__` | CONSTRUYE | `fields.py:1668` |
| leer un `Many2one` calculado procesa su cómputo pendiente | `models.py:_forward_get` | CONSTRUYE | `fields.py:1664-1666` |
| leer un `Many2one` calculado en un registro de `new()` sin valor lo calcula | `models.py:_forward_get` | CONSTRUYE | `fields.py:1736-1763` |
| U4b: `skill_id`/`skill_level_id` `compute` almacenados y editables | `hr_individual_skill_mixin.py` | porte | `hr_individual_skill_mixin.py:47-50`, `:232-248` |

Sin migración: `makemigrations --check` sobre `hr_skills` y
`hr_recruitment_skills` → «No changes detected».

## 6. Corrección de una prueba (protocolo)

1. **Expectativa anterior.** `test_skill_and_level_are_computed_from_the_type`
   creaba `hr.job.skill` sin `skill` ni `skill_level` y esperaba que el
   `create` los calculara.
2. **Evidencia de su error.** En la fuente los dos campos son
   `required=True` (`hr_individual_skill_mixin.py:47-50`) — NOT NULL
   (`odoo/orm/fields.py:298`) — y no `precompute` (`:287`; sólo un campo
   `precompute=True` se calcula antes del `INSERT`, `models.py:4814-4844`).
   Un `create` sin ellos viola el NOT NULL también allá; el cálculo sucede en
   un registro de `new()` (formulario) o al escribir la dependencia.
3. **Expectativa corregida.** `env['hr.job.skill'].new({'skill_type': …})`
   y lectura de `skill`/`skill_level`.
4. **Resultado.** Verde con la rama de `new()` de `_forward_get`.
5. **Control discriminante.** Retirar esa rama (`m2o-new-compute`) o el
   orden caché-antes-que-`__dict__` (`m2o-cache-first`) tumba exactamente
   esta prueba.

Las pruebas de rechazo de hr_skills usaban `transaction.atomic()` suelto:
ahora usan `assert_raises`, que es el arnés de la fuente y además vacía la
transacción del ORM al abrir y al cerrar.

## 7. Controles de anulación (sobre el árbol del gate 2 menos cada pieza)

`probes` en el scratchpad de la sesión (`nul2.py`); subconjunto
`tests/unit/hr_skills`, `test_orm/test_constraints.py`,
`tests/unit/service/test_savepoint.py` (30 casos):

| Pieza retirada | Caen |
|---|---|
| lectura `Many2many` hacia Django | `test_15_constraint`, `test_a_many2many_towards_django_rows_reads_as_their_recordset` |
| `AccessQuerySet.__sub__` | `test_15_constraint`, `test_recordset_algebra_on_django_rows` |
| `QuerySet` → `Command.set` | `test_15_constraint` |
| vaciado al abrir el savepoint | `test_opening_flushes_the_transaction` |
| recómputo al leer `Many2one` | `test_changing_the_type_recomputes_the_skill` |
| cómputo en `new()` | `test_skill_and_level_are_computed_from_the_type` |
| caché antes que `__dict__` | `test_skill_and_level_are_computed_from_the_type` |
| descriptor del `Many2one` calculado | `test_changing_the_type_recomputes_the_skill` |
| validación en `_create` | 4 de creación de hr_skills (control previo) |
| validación en `write` | 2 de escritura de hr_skills (control previo) |
| comparación por campo | 2 que declaran `skill_id` (control previo) |

Dos controles **sobrevivieron** y no se aceptaron:
- `clear()` en `_FlushingSavepoint.rollback`: redundante, el corte
  `savepoint_rollback` ya vacía la transacción. **Retirado**; se cita el
  mecanismo existente.
- descarte del objeto en `_state.fields_cache` cuando la clave cambió: sin
  camino medible (el recómputo ocurre sobre la instancia que lee y el
  `__set__` de Django ya invalida esa copia). **Retirado**: no se deja código
  sin control que lo discrimine.

## 8. Pendiente

1. `test_15_constraint_inverse` y el modelo `test_orm.compute.inverse`
   (`odoo19c: …/test_orm/models/test_orm.py:544-585`).
2. Separar en `write` la validación de no-inversos e inversos y
   `check_access('create')` tras validar en `_create` (TASK-API-0510).
3. Los tres pares de modelos Django sin el `create`/`write` del ORM
   (H-API-1083).
4. `odoo/tests/` no está porteado (12 archivos, 5 447 líneas); sólo
   `_assertRaises`. Dependencia declarada para las pruebas de referencia que
   usen `Form`, `users`, `warmup`, `TransactionCase`.

## 9. Gate 2 (05:45:05Z) — atribución

`uv run pytest -n 4 -q --reuse-db -p no:randomly`:
**3 failed, 12516 passed, 66 skipped, 4 xfailed, 24 errors** (461 s).

- 5 errores `test_multidb_isolation`: ambiental conocido.
- 21 = `ValidationError: Author must be among the discussion participants`
  en fixtures de `read_group*`, `read_grouping_sets`,
  `test_search_returns_query`, `test_one2many::test_commands_on_a_declared_one2many`.
  La restricción ya funciona: **datos de prueba que violan una restricción
  legítima**. Ver §10.
- 1 = **regresión real**: `test_compute_stored_many2one_one2many`
  (`member_count` no bajaba a 0). Ver §11.

## 10. Corrección de fixtures (protocolo)

1. **Expectativa anterior.** Los fixtures creaban `test_orm.message` en
   discusiones sin participantes, con `env` de superusuario sin fila de
   usuario: `author` (por defecto `env.user`) quedaba vacío.
2. **Evidencia.** En la fuente `env.user` siempre existe
   (`TransactionCase`: `api.SUPERUSER_ID`, `odoo/tests/common.py:1192`) y
   `_check_author` (`test_orm.py:177-180`) exige que el autor esté entre los
   participantes; `test_15_constraint` parte de `discussion_0`, cuyo dato de
   demostración incluye al usuario. Los fixtures sólo pasaban porque la
   restricción nunca corría.
3. **Expectativa corregida.** Fixture compartido `system_user`
   (`tests/conftest.py`) para que `env.user` exista, y discusiones con
   `participants = [env.user]`. No se tocó la restricción ni su alcance.
4. **Resultado.** 488 passed en el subconjunto derivado (§12).
5. **Control.** Retirar los participantes vuelve a dar la `ValidationError`
   (es la falla del gate 2).

## 11. Regresión y causa

`test_compute_stored_many2one_one2many` (≙ `odoo19c: …/tests/test_fields.py:317`).
Medido con sondas:

1. Con el recómputo-al-leer, el recorrido posterior de `modified(['name'])`
   ya resolvía `container_id` con el valor nuevo y el contenedor viejo no
   recibía el recálculo de `member_count`. El verde anterior dependía de leer
   el valor viejo de la caché.
2. La fuente marca ese contenedor con `modified(fnames_modifying_relations,
   before=True)` antes de escribir (`models.py:4400-4418`, `:4460`); nuestro
   `RecordLoaderMixin.write` sólo lo hacía para relacionales protegidos.
   **Portado** con `registry.is_modifying_relations` (TRAE).
3. Una instancia distinta de la que calcula conservaba el objeto viejo en
   `_state.fields_cache` (también `None`). **Restaurado** el descarte que en
   §7 se había retirado por no tener camino: este caso es su control.

`Many2one.write` con `_remove_inverses`/`_update_inverses`
(`fields_relational.py:400-424`) se portó y su control **sobrevivió**: aquí
las líneas inversas en caché sólo se leen para registros de `new()`, y la rama
`NewId` de `FieldDescriptor.__set__` ya las actualiza; para registros
guardados el `One2many` se lee de la base. **Retirado** sin camino
observable; queda como obligación ligada a TASK-API-0510 (caché de `_write`).

## 12. Controles de anulación adicionales (árbol del gate 3)

| Pieza retirada | Caen |
|---|---|
| pasada `before` de `is_modifying_relations` | `test_compute_stored_many2one_one2many` |
| descarte de `fields_cache` (incl. `None`) | `test_compute_stored_many2one_one2many` |

Gate 3 lanzado 06:04:59Z sobre `outputs/gate3-hashes.txt`.

## 13. Corrección de una cita

Este banco citaba `TASK-API-0504` como dueña del flujo de escritura. Leído el
store de Thyrox en sólo lectura (`citation_id`), `TASK-API-0504` es «Unidad
6e-2: decodificar jsonb en las consultas crudas»; el flujo
`_write`/`_write_multi`/`_flush` es **`TASK-API-0510`**. Las citas de este
banco y de H-API-1212 se corrigieron a `TASK-API-0510`.
