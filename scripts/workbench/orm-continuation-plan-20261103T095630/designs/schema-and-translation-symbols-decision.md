# Símbolos de esquema y de traducción de `BaseModel` — matriz de equivalencia

Fecha: 2026-11-10. Referencia: odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`, `odoo19c: odoo/orm/models.py`.
Clasificación: `outputs/obligation_classification.tsv`, los seis
`absent / task_without_unit` bajo TASK-API-0485.

## Lo medido

| Símbolo | Referencia | Llamador en la fuente | Aquí |
|---|---|---|---|
| `_auto_init` | `:3170-3248` (79 líneas) | `registry.init_models` (`registry.py:751`) | `migrate` de Django crea y altera tablas; `_check_parent_path` ya vive en `check()` |
| `_check_removed_columns` | `:3109-3136` | `_auto_init` (`:3217`), `modules/loading.py:518` | sin equivalente: ninguna pieza quita el `NOT NULL` de una columna que el modelo ya no declara |
| `_add_sql_constraints` | `:3262-3268` | `_auto_init` (`:3244`) | `TableObject.apply_to_database` existe (`src/orm/table_objects.py:236,294,390`) y `_table_objects` también (`models.py:6101`), pero `apply_to_database` no tiene llamador fuera de pruebas: las restricciones van por `Meta.constraints` y migraciones |
| `get_field_translations` | `:3664-3703` | vistas y `web` | `translate=True` sólo se anota; la columna es `varchar` de un idioma (`models.py`, `copy_translations`) |
| `update_field_translations` | `:3492-3503` | `copy_translations`, `web` | ídem |
| `_update_field_translations` | `:3504-3663` (160 líneas) | `update_field_translations` | ídem |

## Corrección del 2026-11-10

La primera versión de este archivo terminaba en «opciones para el
ejecutor». Directiva del ejecutor del mismo día: la referencia, el stack y
los consumidores permiten derivar la decisión; no se trasladan opciones que
no demuestran cuál satisface el contrato. Lo medido arriba se conserva; lo
que sigue la reemplaza.

## Evidencia medida (2026-11-10, base de pruebas construida por `migrate`)

- **Autoridad del esquema.** `init_models` (`src/orm/registry.py:2323`) y
  `Field.update_db` (`src/orm/fields.py:3413`) están portados y **no
  tienen llamador** fuera de pruebas (grep sobre `src/` y `addons/`). La
  carga de módulos declara *"the caller owns schema readiness"*
  (`src/modules/loading.py:1-7`), y el estado `to remove` nunca se ejecuta:
  `reset_modules_state` lo devuelve a `installed` (`:44-46`). La única
  autoridad que crea y altera tablas son las migraciones de Django.
- **Modelos y migraciones en sincronía:** `makemigrations --check
  --dry-run` → *"No changes detected"*, exit 0.
- **Sonda de efectos observables de la referencia** sobre 440 modelos con
  tabla ordinaria (`scratchpad/probe-schema-effects.py`):
  columnas de la tabla que el modelo no declara **0** (y con `NOT NULL`,
  **0**); columnas declaradas que faltan **0**; `required` contra
  `NOT NULL` **3** discrepancias, las tres `GeneratedField` (`*_key`), a
  las que Django no pone `NOT NULL` y que la referencia no tiene;
  objetos de tabla declarados ausentes en PostgreSQL **1 de 1**
  (`test_orm_category_positive_color`).
- **Causa del objeto ausente:** `TableObject.to_django()` no tiene
  llamador (`src/orm/table_objects.py`). Su docstring promete que
  `Meta.constraints`/`Meta.indexes` lo materializan con `makemigrations`,
  pero nada lo coloca ahí, y `_table_objects` queda en su valor por defecto
  vacío (`models.py:6101`). Todos los consumidores leen `Meta`: el mensaje
  de error (`_table_object`, `models.py:274-281`), el reflejo en
  `ir.model.constraint` (`ir_model.py:2335-2370`) y las migraciones.
- **Ningún guardián de la sincronía:** ni la CI (`api-tests.yml`), ni el
  `pre-commit`, ni ninguna prueba ejecutan `makemigrations --check` ni el
  autodetector.
- **Traducciones:** 14 campos `translate=True`, todos `CharField` sobre
  `varchar`, en 12 tablas de 7 apps (`outputs/translate-fields.tsv`);
  ninguno con traducción por términos.

## Matriz

| Contrato de referencia | Revisión | Consumidores en la referencia | Comportamiento exigido | Mecanismo Django existente | Capacidad PostgreSQL | Divergencia observada | Implementación elegida | Migración | Consumidores afectados | Pruebas discriminantes | Verificación | Obligación restante |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `_auto_init`: tabla, columnas, tipo, `NOT NULL`, índices (`:3170-3236`, `Field.update_db`) | `abe4040ec1` | `registry.init_models` (`registry.py:751`) | el esquema refleja los campos declarados | `makemigrations` + `migrate` | DDL transaccional | ninguna en el estado (0 columnas faltantes u huérfanas; sincronía limpia); **sí** en la garantía: nada impide que un modelo cambie sin migración | contrato **satisfecho por mecanismo equivalente**; corrección mínima: prueba que exige `makemigrations --check` limpio | ninguna | toda app | `test_migrations_in_sync.py` (proceso aparte; sin la migración `0041` de `test_orm` cae y la nombra) | sonda + `makemigrations --check`; guardián verde | **TASK-API-0515**: implementado, pendiente de gate |
| `_auto_init`: marcar para cómputo los calculados almacenados nuevos sobre filas existentes (`:3229-3238`) y `parent_path` nuevo (`:3201-3204`, `:3246-3247`) | ídem | ídem | una columna calculada nueva se calcula sobre las filas que ya existen | `AddField` deja `NULL` o el default; ningún `post_migrate` recalcula | — | **ausencia funcional** (ningún mecanismo) | no se cablea `_auto_init`: se añade el cálculo como paso de la migración que introduce la columna (`RunPython` con `_recompute`/`_parent_store_compute`), la misma autoridad | por migración que añada un calculado almacenado | apps que añadan calculados | migración de prueba sobre filas existentes | pendiente | **TASK-API-0516** (unidad aparte) |
| `_check_removed_columns` (`:3109-3136`) | ídem | `_auto_init` (`:3217`), `modules/loading.py:518` | una columna que el modelo ya no declara pierde su `NOT NULL` (desinstalación, campo retirado) | retirar un campo genera `RemoveField`, que borra la columna (más fuerte); la desinstalación no retira código | — | 0 columnas huérfanas; la equivalencia depende de la misma sincronía | **satisfecho por mecanismo equivalente**, divergencia estructural declarada (se borra la columna en vez de relajarla); el guardián de sincronía lo protege | ninguna | — | la misma prueba de sincronía (un campo retirado sin migración la tumba) | sonda | cubierta por TASK-API-0515 |
| `_add_sql_constraints` (`:3262-3268`) | ídem | `_auto_init` (`:3244`); el mensaje de error lee `_table_objects` (`:3275`) | todo objeto de tabla declarado existe en la base con su `full_name` y su mensaje llega al error | `Meta.constraints`/`Meta.indexes` + migraciones; `add_meta_index` (`model_classes.py:835`) ya escribe `Meta` y `original_attrs` | `ADD CONSTRAINT`, `CREATE INDEX` | **real**: el objeto declarado con la forma de la referencia nunca llega a `Meta`, ni a migración, ni a la base, ni al mensaje (1 de 1) | puente en `class_prepared` (≙ paso 7 de `model_classes._setup`, `odoo19c: model_classes.py:455-461`): `to_django()` a `Meta` por la vía de `add_meta_index` + hermano `add_meta_constraint`, y `_table_objects` por `full_name`; **no** se cablea `apply_to_database` (sería una segunda autoridad) | `AddConstraint` en `test_orm` | `test_orm.category`, `_sql_error_to_message`, `ir.model.constraint` | `test_table_objects_reach_meta.py`: RED 4/4 (con `color = -1` aceptado por PostgreSQL); GREEN 4/4; sin el receptor caen 1, 2 y 4, sobrevive 3 (depende de la migración aplicada) | regresión derivada 6296 passed (el único rojo era el guardián en proceso, corregido) | **TASK-API-0514**: implementado, pendiente de gate |
| `get_field_translations`, `update_field_translations`, `_update_field_translations` (`:3492-3703`) | ídem | `web` (diálogo de traducciones), `copy_translations` (`:5465-5528`), importación | columna `jsonb {lang: valor}`, lectura por `lang` con respaldo `en_US`, escritura de un idioma conservando los demás | `JSONField`, `django.contrib.postgres` cableado | `jsonb`, operadores `->>`, `||`, índices de expresión | **ausencia funcional**: `translate=True` sólo se anota; 14 columnas `varchar` | se construye el eje `translate` del campo sobre `JSONField` (sin capa paralela), y los tres métodos encima | `varchar` → `jsonb` en 14 columnas, con conservación del valor actual bajo `en_US` | 7 apps, `copy_translations`, búsquedas por campo traducible | migración con filas existentes, lectura por idioma, escritura que conserva idiomas | implementado en `febd56b3` (RED/GREEN/anulación en `translate-jsonb-storage.md`); aceptación pendiente del gate | **TASK-GEN-0060** (existente), con TASK-GEN-0436 |

## TASK canónica de traducciones

`#333` no es una cita: en el store resuelve a `TASK-GEN-0648` (*Keep
mutation-test markers out of thyrox's own commits*), otro sujeto. Las
existentes que cubren la obligación, medidas en el store del proveedor:

- **TASK-GEN-0060** — *Construir el almacenamiento jsonb de
  translate=True* (`pending`, bloquea a `#400`): (a) campo `jsonb` con
  lectura y escritura por idioma, (b) reescritura de consulta, (c)
  migración de los `varchar`. Es la canónica.
- **TASK-GEN-0436** — *Construir el eje translate del ORM, hermano de
  company_dependent*: el mismo eje por el lado del campo.
- Relacionadas, no la misma obligación: TASK-API-0375 (catálogo `.po` por
  addon), TASK-GEN-0062 (motor `.po`), TASK-API-0283 (`field_description`
  sin `translate=`).

`copy_translations` (`models.py`) se corrige para citar TASK-GEN-0060 en
lugar de `#333`.

## Resultados de TASK-API-0514 y TASK-API-0515 (2026-11-10)

- Puente: receptor `determine_table_objects` en `class_prepared`
  (`src/orm/model_classes.py`), con `add_meta_constraint` hermano de
  `add_meta_index`. `makemigrations --dry-run` propuso exactamente una
  operación: `AddConstraint test_orm_category_positive_color`, emitida como
  `src/addons/test_orm/migrations/0041_category_positive_color.py`.
- Guardián: la primera forma corría `makemigrations` dentro del proceso de
  pytest y, en la regresión, contó como cambios los modelos de sondeo que
  los módulos de prueba registran en `apps` (`CacheProbe`,
  `ComputeDispatchProbe`…) y `AccountInvoiceReport`. Corre ahora en un
  proceso aparte, como `manage.py makemigrations --check`: verde junto a
  esos módulos, rojo sin la migración `0041`.
- `AccountInvoiceReport` no se registra al cargar `account` (H-API-682,
  preexistente): queda fuera del guardián y de esta unidad.

## Revisión del 2026-11-10T22:14:39 — los tres símbolos se portan con su contrato

**Qué se revisa.** La matriz de arriba declara `_auto_init` y
`_check_removed_columns` «satisfechos por mecanismo equivalente», y
`_add_sql_constraints` resuelto por el puente a `Meta`, sin receptor en
`init_models` (`orm/registry.py:2332-2340`). La directiva del ejecutor
(«Continuidad persistente…», §9) prohíbe declarar una divergencia para no
implementar, y la anterior manda que una divergencia que existía por faltar
la raíz ORM se implemente como la referencia. El inventario los cuenta
`absent` (`outputs/line-reconciliation-20261110.md`, línea 12-13). La
historia de arriba se conserva: la decisión de no crear una segunda
autoridad sigue en pie y gobierna esta revisión.

**Contrato** (`odoo19c: odoo/orm/models.py`, `abe4040ec1`):
`_check_removed_columns` (:3109-3136) quita el `NOT NULL` de toda columna
de la tabla que el modelo ya no declara como almacenada; `_auto_init`
(:3170-3248) crea la tabla si falta, llama a `_check_removed_columns` si
ya existía, pone al día cada columna con `Field.update_db`, marca para
cómputo los calculados nuevos sobre filas existentes, aplica
`_add_sql_constraints` y calcula `parent_path` si la columna es nueva;
`_add_sql_constraints` (:3262-3268) aplica cada objeto de
`_table_objects` con `apply_to_database`. Los llama `init_models`
(`odoo/orm/registry.py:751`), modelo a modelo, seguidos de `init()`.

**TRAE / CONSTRUYE.** Todo lo que tocan existe: `tools.sql` porta
`table_exists`, `create_model_table`, `table_columns`, `column_exists`,
`create_column` y `drop_not_null`; `orm/table_objects.py` porta los tres
`apply_to_database`; `_table_objects` lo llena el puente de TASK-API-0514.
Se CONSTRUYE sólo el receptor: los tres métodos en `BaseModel` y su
llamada desde `Registry.init_models`, por el alias del registro (L4f).

**Por qué no es una segunda autoridad.** `init_models` corre en
`post_migrate`, después de `migrate`. Con el guardián de sincronía
(`test_migrations_in_sync.py`) la tabla, las columnas y los objetos ya
existen, y cada paso de la fuente comprueba antes de actuar: crear sólo si
falta, `update_db` sólo si la columna difiere, `apply_to_database` sólo si
la definición difiere, `drop_not_null` sólo sobre columnas que el modelo no
declara. Su efecto normal es nulo y medible; actúa sólo donde `migrate` no
llega —columnas de otro módulo desinstalado, objetos de tabla declarados sin
migración—, que es lo que la fuente le encarga.

**Orden de implementación**, cada paso con RED/GREEN y anulación:

| # | Pieza | Prueba |
|---|---|---|
| s1 | `_check_removed_columns` | columna huérfana `NOT NULL` → queda anulable; una declarada no se toca |
| s2 | `_add_sql_constraints` | un objeto de tabla ausente en la base se crea; uno presente no se recrea |
| s3 | `_auto_init` | sobre el esquema sincronizado no emite DDL; una columna huérfana pierde el `NOT NULL` |
| s4 | receptor en `init_models` (`_auto_init` + `init`) por alias | la instalación lo llama una vez por modelo `_auto` |

### s1 — resultado (2026-11-10T22:18:27)

`_check_removed_columns` portado en el mixin del cargador (lo adopta todo
modelo concreto vía `TimeStampedModel`), `classmethod` con `using`.
`tests/unit/orm/test_schema_auto_init.py`: RED 2/2 (sin el método), GREEN
2/2. Anulaciones: sin `drop_not_null` cae sólo
`test_an_orphan_column_loses_its_not_null`; sin el filtro de columnas
declaradas cae sólo `test_a_declared_column_keeps_its_not_null`.

### s2 — alcance medido antes de implementar (2026-11-10T22:18:27)

`_add_sql_constraints` es una línea, pero lo que llama no tiene el contrato
de la fuente:

| Pieza | Fuente (`odoo/orm/table_objects.py`) | Aquí | Defecto |
|---|---|---|---|
| `Constraint.apply_to_database` | `:109-122`: compara `constraint_definition`; igual → nada; distinta → `drop_constraint` y `post_constraint(add_constraint)` | `orm/table_objects.py:294`: `editor.add_constraint` siempre, por `connection` (alias por defecto) | no es idempotente: sobre una base migrada choca con la restricción existente; y escribe en la base equivocada |
| `Index.apply_to_database` | `:154-185`: compara `index_definition` y su comentario; igual → nada; distinta → `drop_index` y `post_constraint(add_index)` | `:390`: `editor.add_index` siempre | ídem |
| `sql.add_constraint` | deja `COMMENT ON CONSTRAINT … IS <definición>` | portado así (`tools/sql.py:824`) | — |
| `RawConstraint.create_sql` (la migración) | — | `ADD CONSTRAINT` sin comentario | una restricción creada por migración no lleva la definición declarada, y `constraint_definition` devuelve la normalizada de `pg_get_constraintdef`: la compararía distinta y la recrearía |

Primitivas ya portadas (TRAE): `constraint_definition`, `add_constraint`,
`drop_constraint`, `index_definition`, `add_index`, `drop_index`,
`Registry.post_constraint`/`finalize_constraints`.

CONSTRUYE: los dos `apply_to_database` con el contrato de la fuente, por el
alias que se les pase; `RawConstraint.create_sql` y `RawIndex` dejan el
mismo comentario que `sql.add_constraint`/`sql.add_index`, para que
migración y conciliación lleguen al mismo estado. Una base ya migrada sin el
comentario se recrea **una vez** con la misma definición y desde ahí es
estable; se declara aquí y se mide.

## Autoridad del esquema — contrato (2026-11-10T22:36:12)

Directiva del ejecutor del mismo día, §5: definir la autoridad antes de
conectar `_auto_init` al ciclo.

**Los dos flujos, sin presuponerlos iguales.**

| Paso | Odoo 19 (`odoo/modules/loading.py`, `registry.py:751`) | Kaupamex |
|---|---|---|
| instalar un módulo | `load_module_graph`: `registry.load` → `init_models` → `load_data` | `kaupamex-bin`/`migrate` aplica las migraciones; `post_migrate` → `load_modules` → `init_models` → `load_data` (L3) |
| crear tabla y columnas | `_auto_init` (`create_model_table`, `Field.update_db`) | las operaciones de la migración (`CreateModel`, `AddField`, `AlterField`) |
| restricciones e índices | `_add_sql_constraints` → `apply_to_database` → `post_constraint` | `Meta.constraints`/`Meta.indexes` (puente de TASK-API-0514) → `AddConstraint`/`AddIndex` |
| calculados almacenados nuevos | `_auto_init` marca y `env.add_to_compute` | `ComputeStoredFields` dentro de la migración (TASK-API-0516) |
| estado declarado del esquema | ninguno aparte de la base | `django_migrations` + el estado que reconstruye `makemigrations` |

**La autoridad es la migración.** Es lo único que Django reconstruye como
estado (`makemigrations` lo compara con los modelos) y lo único que el
guardián `test_migrations_in_sync.py` mantiene igual al código. Todo cambio
de forma del esquema —tabla, columna, tipo, restricción, índice— nace como
operación de migración.

**Qué puede hacer la conciliación** (`_auto_init` y familia), y por qué no
es una segunda autoridad: sólo actúa sobre lo que el estado de migraciones
**no modela** o sobre una base que **se apartó** de ese estado, y en ambos casos
lleva la base hacia el estado de migraciones, nunca a otro.

| Situación | Fuente | Aquí | Por qué no compite con `migrate` |
|---|---|---|---|
| tabla de un modelo `_auto` ausente | la crea | **error nombrado**: falta su migración | crearla fuera de `migrate` dejaría a `django_migrations` sin la tabla que existe |
| columna que el modelo ya no declara, con `NOT NULL` | `drop_not_null` (s1) | igual | ninguna migración la modela: `RemoveField` la habría borrado; es una columna fuera del estado |
| columna declarada con forma distinta | `update_db` la altera | **se informa**, no se altera | alterarla divergiría del estado; el guardián exige la migración |
| objeto de tabla ausente en la base | lo crea | lo crea con la definición declarada | el estado de migraciones dice que existe (lo creó `AddConstraint`): reponerlo devuelve la base a ese estado |
| objeto presente y equivalente | nada | nada; si le falta el comentario con su definición, se le añade (metadato, sin DDL de forma) | no cambia la forma |
| objeto presente con definición distinta | lo borra y lo recrea | **se informa**, no se recrea | la definición nueva llega por `AlterConstraint`/`RemoveConstraint`+`AddConstraint`; recrearlo aquí dejaría la base distinta de lo que el estado de migraciones registra |

**Equivalencia: no se lee del comentario solo.** Se comparan, en este orden:
1) el comentario con la definición declarada (la forma de la fuente, que
`sql.add_constraint` deja); 2) si no hay comentario —objeto creado por
migración—, la forma normalizada: para un `CHECK`, `pg_get_constraintdef`
del objeto existente contra el de la definición declarada, obtenido creándola
`NOT VALID` con un nombre temporal dentro de un punto de guardado que se
deshace (sin recorrer la tabla ni bloquearla más que el `ALTER`); para
`UNIQUE`/`EXCLUDE`/`FOREIGN KEY`, el tipo (`contype`) y las columnas
(`conkey`) contra los de la definición, y si no se puede decidir, se informa.
Un índice sigue la regla de la fuente (`:159`): se conserva si su comentario
coincide **o** si existe sin comentario.

**Medido antes de implementar:** en la base de pruebas, de los objetos
declarados en `_table_objects` de todo el árbol llega **uno**
(`test_orm_category_positive_color`, `CHECK`, sin comentario, con
`pg_get_constraintdef` distinto del texto declarado sólo por normalización).
Los demás `≙ models.Constraint(...)` de los addons están portados a mano como
`Meta.constraints` y no entran en `_table_objects`: es porte de cada addon,
fuera de la raíz, y queda anotado como frontera. El impacto de una recreación
es, por tanto, nulo en esta revisión: la regla de arriba no recrea nada.

**Pruebas exigidas** (`tests/unit/orm/test_schema_auto_init.py`): objeto
ausente; existente y equivalente sin comentario (migración); existente con el
comentario de la conciliación; definición distinta; reejecución sin cambios;
alias de base distinto del por defecto (en la base desechable de ci-multidb).

### s2 — resultado (2026-11-10T22:41:41)

`_add_sql_constraints` portado junto a `_check_removed_columns`;
`Constraint.apply_to_database` e `Index.apply_to_database` con el contrato
de la fuente y la regla de autoridad de arriba (`orm/table_objects.py`). La
forma normalizada de un `CHECK` se sondea con `NOT VALID` y un nombre
temporal dentro de un punto de guardado que se deshace.

| Prueba (`test_schema_auto_init.py`) | Estado inicial | RED | Anulación que la tumba (y sólo a ella) |
|---|---|---|---|
| `test_a_migrated_equivalent_constraint_is_not_recreated` | creada por migración, sin comentario | cae (sin método) | sin la sonda normalizada |
| `test_a_second_run_changes_nothing` | tras la conciliación | cae | — (la cubre la anterior) |
| `test_an_absent_constraint_is_restored` | ausente | cae | sin la reposición del ausente |
| `test_a_different_constraint_is_reported_not_recreated` | definición distinta | cae | recreando en vez de informar |
| `test_an_absent_index_is_created_with_its_comment` | índice ausente | — | — |
| `test_a_second_index_run_changes_nothing` | tras crearlo | — | — |
| `test_an_index_without_comment_is_kept` | índice sin comentario | — | sin la regla `:159`; su primera versión **no discriminaba** (la rama que informa tampoco recrea) y se le añadió que la conservación sea silenciosa |

Subconjunto derivado (`grep` de los símbolos tocados en `tests/`): 201
passed. Pendiente de s2: la base nueva y el alias distinto de `default` —los
cubre ci-multidb al cerrar el bloque, cuando `_auto_init` tenga llamador.

### s3 y s4 — resultado (2026-11-10T22:47:48)

**s3, `_auto_init`.** Portado como conciliación: un modelo abstracto,
proxy o no administrado (`_auto` ≙ `Meta.managed`) se salta; tabla o
columna declarada ausente → `ValueError` que nombra la migración que falta;
`_check_removed_columns` y `_add_sql_constraints` con su contrato.

| Prueba | Anulación que la tumba (y sólo a ella) |
|---|---|
| `test_on_a_synchronised_schema_it_emits_no_schema_ddl` (`CaptureQueriesContext`: 0 `CREATE`/`ALTER`/`DROP`) | — es la prueba de que no hay segunda autoridad |
| `test_it_relaxes_an_orphan_column` | sin `_check_removed_columns` |
| `test_a_missing_declared_column_names_its_migration` | sin la comprobación de columnas |
| `test_a_missing_table_names_its_migration` | sin `table_exists`; su primera forma (`match=TABLE`) **no discriminaba**, porque el error de columnas también nombra la tabla, y se ajustó a `match='Table <tabla> '` antes de ejecutar el control |

**s4, llamador productivo.** `Registry.init_models` llama
`_auto_init(using=<alias del registro>)` en cada modelo antes del reflejo,
como `odoo/orm/registry.py:750-752`. `test_init_models_runs_the_reconciliation`
cae sin la llamada. Efecto observado: la instalación de la sesión de
pruebas ya concilia la base, y la prueba de s2 que suponía el estado
«recién migrado» pasó a fijarlo explícitamente (`COMMENT … IS NULL`).

**s1 integrado.** `_check_removed_columns` tiene ahora llamador productivo
(`init_models` → `_auto_init`), con alias explícito.

### s5 — el gancho `init` (pendiente, medido)

La fuente llama `model.init()` tras `_auto_init` (`registry.py:752`).
`BaseModel.init` está `not_verified` (`unresolved`) y dos modelos lo
sobreescriben con efectos: `ir.config_parameter.init` (siembra parámetros,
alias por defecto en su firma) y `hr.employee.public.init`
(`CREATE OR REPLACE VIEW`, cuyo docstring dice que ningún flujo lo ejecuta y
que su autoridad es una migración `RunSQL` pendiente). Cablear `init` sin
resolver esos dos cambia la conducta de la instalación; queda como unidad
propia: portar `BaseModel.init` (gancho vacío), pasar el alias a los dos
overrides y decidir con medición si la vista de `hr.employee.public` la
crea la migración o el gancho.

### s5 — diseño medido (2026-11-10T23:01:06)

**Contrato.** `BaseModel.init` (`odoo19c: odoo/orm/models.py:3250-3253`):
gancho vacío, «called after `_auto_init`, and may be overridden to create or
modify a model's database schema»; `init_models` lo llama justo después
(`registry.py:752`).

**Medido antes de cablearlo.** Dos modelos lo sobreescriben:

| Modelo | Override | Medición |
|---|---|---|
| `hr.employee.public` (`Meta.managed = False`, ≙ `_auto = False`) | `CREATE OR REPLACE VIEW` sobre `hr_employee`/`hr_version`/`resource_resource`, por `connection` (alias por defecto) | **la vista no existe** en la base de pruebas (`pg_class` vacío): hoy nadie llama a `init` y `hr.employee.public` no se puede leer. Su SQL, ejecutado dentro de una transacción deshecha, crea la vista y `HrEmployeePublic.objects.count()` responde |
| `ir.config_parameter` | siembra los parámetros ausentes (idempotente), ya con `using` | la siembra de migración y `_SEEDERS` ya los dejan; volver a llamarlo no cambia nada |

**TRAE / CONSTRUYE.** CONSTRUYE el gancho vacío en el mixin del cargador
(`classmethod init(cls, using=None)`), la llamada en `init_models` tras
`_auto_init` con el alias del registro, y el alias en el override de
`hr.employee.public` (`connections[using]`). La vista es un objeto que el
estado de migraciones **no modela** (modelo no administrado): crearla aquí no
compite con `migrate`, que es la regla de la autoridad del esquema.

**Pruebas.** `init_models` sobre `hr.employee.public` crea la vista en la base
del registro; el gancho base no emite nada; reejecutar `init` es idempotente
(`CREATE OR REPLACE`). Control: sin la llamada en `init_models`, la vista no
existe.

### s5 — resultado (2026-11-10T23:07:10)

- **Medido al implementar:** `hr.employee.public` es un modelo de Django
  sin el mixin del cargador (no tiene `_auto_init`). En la fuente todo
  modelo tiene `init`, así que `init_models` llama `init(using=…)` en
  cualquier modelo que lo declare, haya o no `_auto_init`.
- **Llamador productivo:** `install_cycle` → `modules.loading.load_modules`
  → `Registry.init_models` (`src/modules/loading.py:239`).
- **Una sola autoridad por vista:** `res.device` no sobreescribe `init` (su
  vista la crea `base.0004`); `hr.employee.public` no tiene migración que
  la cree. Ningún objeto queda con dos creadores.
- **Pruebas** (`tests/unit/orm/test_schema_auto_init.py`, 3 nuevas): el
  gancho base no emite SQL; `init_models` crea la vista; un segundo `init`
  la conserva. Suite del archivo: 17 passed.
- **Anulación:** sin `model.init(...)` en `init_models` cae exactamente
  `test_init_models_creates_the_view_of_an_unmanaged_model`; con un gancho
  base que ejecuta SQL cae exactamente `test_the_base_init_hook_emits_nothing`.
  En las dos, 16 siguen en verde.
- *Ciega a:* que la vista caiga en la base del alias y no en la de por
  defecto; eso lo mide el ci-multidb, no esta suite.

### s5 — contrato completo de `init` en la fuente, y lo que faltaba (2026-11-10T23:42:38)

Derivado de `odoo19c` (odoo-tools `abe4040ec1`):

| Aspecto | Fuente | Aquí |
|---|---|---|
| Invocación | `init_models` (`registry.py:749-751`): `for model in models: model._auto_init(); model.init()`, sobre **todos** los modelos del módulo, sin filtrar | igual: `init` en todo modelo que lo declare, haya o no `_auto_init` |
| Orden | justo después del `_auto_init` **del mismo modelo**, antes de los `_reflect_*` y de la cola `_post_init_queue` | igual |
| Abstractos / `_auto = False` | se llama también (el `_auto_init` de un abstracto no hace nada; `init` sí corre) | igual: un modelo `managed = False` pasa por `init` |
| Gancho base | vacío, `@api.private` (`models.py:3250-3253`) | vacío, sin SQL (prueba `test_the_base_init_hook_emits_nothing`) |
| Vistas SQL | `drop_view_if_exists` y luego `CREATE or REPLACE VIEW` (`hr_employee_public.py:195-203`, `res_device.py:230`) | **faltaba** `drop_view_if_exists`: una vista previa con otras columnas no admite `REPLACE`. Corregido (prueba `test_init_replaces_a_view_with_another_column_set`, rojo con «cannot change name of view column») |
| Reejecución | cada instalación o actualización del módulo vuelve a llamarlo; los overrides son idempotentes | igual |
| Base / alias | el `cr` del `Environment` de esa base | `using` = alias del registro (`Registry._alias()`) |
| Transacción | la del ciclo de carga: un error en `init` aborta la carga del módulo | `load_modules` envuelve `init_models` en `transaction.atomic(using=…)`: un error revierte el paso del módulo |
| Dependencias | la vista lee `hr_employee`/`hr_version`; las tablas ya existen porque sus módulos se cargan antes en el grafo | igual (grafo de `load_modules`) |

**Otros `init` de la fuente en `base`, sin porte (barrido del archivo):**

| Modelo | Qué hace en la fuente | Estado aquí |
|---|---|---|
| `ir.logging` (`ir_logging.py:36`) | retira `ir_logging_write_uid_fkey` | pendiente de medir si esa FK existe aquí |
| `res.company` (`res_company.py:102`) | asigna `paperformat_euro` a compañías sin formato | pendiente: depende del porte de `paperformat_id` |
| `res.users` (`res_users.py:277`) | cifra las contraseñas en claro escritas por SQL | divergencia de mecanismo candidata: el cifrado lo hace `django.contrib.auth`; falta declararla en el archivo |
| `res.users.apikeys` (`res_users.py:1531`) | `CREATE TABLE IF NOT EXISTS` de su tabla | pendiente de medir contra la migración que crea la tabla |
| `res.device` (`res_device.py:230`) | crea su vista | la crea `base.0004` (`RunSQL`); no se duplica en `init` |

**Prueba multidb discriminante** (`tests/integration/company/test_multidb_isolation.py::
test_init_creates_the_view_only_in_the_selected_database`):
el aprovisionamiento de cada base de empresa deja la vista; tras retirarla,
`init(using=A)` la crea en A, **no** en B, y no cambia la base por defecto;
reejecutarlo conserva el estado. Se ejecuta sólo en el gate ci-multidb, que
es el que aporta las dos bases desechables: el gate genérico no la contiene.
Control: con el override escribiendo por la base por defecto, la vista no
aparece en A.

**Propietario único:** `hr.0009_hremployeepublic` declara `managed: False`
y no tiene `RunSQL`; ninguna migración de `hr` crea la vista. Su único
creador es `init`.
