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
| `get_field_translations`, `update_field_translations`, `_update_field_translations` (`:3492-3703`) | ídem | `web` (diálogo de traducciones), `copy_translations` (`:5465-5528`), importación | columna `jsonb {lang: valor}`, lectura por `lang` con respaldo `en_US`, escritura de un idioma conservando los demás | `JSONField`, `django.contrib.postgres` cableado | `jsonb`, operadores `->>`, `||`, índices de expresión | **ausencia funcional**: `translate=True` sólo se anota; 14 columnas `varchar` | se construye el eje `translate` del campo sobre `JSONField` (sin capa paralela), y los tres métodos encima | `varchar` → `jsonb` en 14 columnas, con conservación del valor actual bajo `en_US` | 7 apps, `copy_translations`, búsquedas por campo traducible | migración con filas existentes, lectura por idioma, escritura que conserva idiomas | pendiente | **TASK-GEN-0060** (existente), con TASK-GEN-0436 |

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
