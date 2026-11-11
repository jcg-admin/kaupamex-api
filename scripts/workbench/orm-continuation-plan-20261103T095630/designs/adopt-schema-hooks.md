# Unidad: todo modelo recibe los métodos de esquema (`adopt_schema_hooks`)

Diseño medido el 2026-11-11T00:14:10 sobre `3d7faad3`.

## Por qué: la corrección del censo por comportamiento

El censo dejó s1–s5 en `not_verified` porque `_auto_init`,
`_check_removed_columns`, `_add_sql_constraints` e `init` viven en
`RecordLoaderMixin` y no en `BaseModel`. Medido por resolución de métodos,
no por nombre:

- la clase `BaseModel` no tiene ninguno de los cuatro en su MRO;
- los **63** modelos concretos que derivan de `BaseModel` heredan también
  `RecordLoaderMixin` (0 sin él): todos los reciben;
- de los 445 modelos administrados, **94** no tienen `_auto_init`: 7 de
  Django contrib y **87 propios** (`base.ResCountry`, `base.ResLang`,
  `base.DecimalPrecision`, 33 de `account`, 4 de `analytic`…);
- `Registry.init_models` llama `_auto_init` sólo si existe
  (`hasattr`), así que esos 87 se saltan la conciliación sin avisar.

En la fuente **todo** modelo pasa por `_auto_init` e `init`
(`registry.py:749-751`). El contrato se cumple en 351 modelos y falta en
87. No es una divergencia de propietario: es una cobertura parcial.

## Search Existing → REUSE/EXTEND

La autoridad que ya posee «dar a todo modelo propio lo que en la fuente
cuelga de `BaseModel`» es `orm.model_classes`: `adopt_display_name`,
`adopt_access_manager` y `adopt_base_url`, cada uno con su receptor de
`class_prepared` y su barrido `ensure_*`, que llama
`addons/base/apps.py`. Mismo discriminador: excluye abstractos, proxies y
módulos de terceros (`THIRD_PARTY_MODULE_PREFIXES`), y sólo cuelga lo que
el modelo no resuelve ya por MRO (`getattr(...) is None`).
**Decisión: EXTEND**, con `adopt_schema_hooks` y `ensure_schema_hooks`. No
se construye otro mecanismo.

## Riesgo medido antes de conectar

Comprobación de solo lectura, con la lógica de `_auto_init`, sobre los 87:
**0** lanzarían `ValueError`. Todos tienen su tabla y todas sus columnas
concretas.

## Pruebas (RED primero)

1. `base.ResCountry` resuelve `_auto_init`, `_check_removed_columns`,
   `_add_sql_constraints` e `init` hasta la implementación de
   `RecordLoaderMixin`.
2. Un modelo que declara su propio `init` (`hr.employee.public`) lo
   conserva.
3. `ensure_schema_hooks()` deja **0** modelos propios administrados sin
   `_auto_init` (contra 87 hoy).
4. `init_models` sobre `base.res.country` concilia una columna huérfana
   `NOT NULL` (`_check_removed_columns`).
5. Anulación: sin la llamada en el barrido y sin el receptor, cae el caso 3
   y vuelve a haber 87.

## Integración

El barrido corre en `BaseConfig.ready()`, junto a `ensure_display_names`.
El ciclo de instalación ya llama a `init_models` (s4). Con esto los 87
modelos entran en la conciliación del esquema.

## Clasificación medida y garantías del mecanismo (2026-11-11T00:46:33)

Probe `probes/schema_hooks_census.py`, salida en
`outputs/schema_hooks_census.out`. Modelos propios sin `_auto_init`: **91**.

| Clase | Modelos | Qué harían los cuatro métodos hoy |
|---|---|---|
| administrados, con migración aplicada de su app | 87 | `_auto_init` comprueba la tabla y las columnas (0 faltan); `_check_removed_columns` no toca nada (0 columnas huérfanas `NOT NULL`); `_add_sql_constraints` no toca nada (0 objetos de tabla); `init` es el gancho vacío. **Ningún efecto SQL** |
| no administrados | 4 | `_auto_init` sale por `managed = False`; `init` propio si lo declaran |
| abstractos o proxy | 0 | — |
| con `init` propio | 2 (`base.SystemParameter`, `hr.HrEmployeePublic`) | se conserva: el discriminador `getattr` lo ve resuelto |

Propietario del esquema: en los 91, la migración de su propia app. La
adopción **no** crea una segunda autoridad. La conciliación sólo detecta
deriva (tabla o columna sin migración) y retira el `NOT NULL` de una
columna que el modelo ya no declara, que es lo que la migración no modela.
Hoy no cambia ninguna fila de ninguna tabla. Su valor es la detección
futura y la cobertura del ciclo de instalación.

**Garantías de `class_prepared`, medidas en el precedente
`adopt_display_name`:**

- La señal se emite al final de `ModelBase.__new__` (`_prepare`), una vez
  por clase concreta, abstracta o proxy, antes de que el registro de apps
  esté listo. `adopt_schema_hooks` no consulta el registro: sólo cuelga
  atributos de clase.
- Herencia: una subclase cargada después recibe su propia señal. Si su
  padre ya adoptó los métodos, `getattr` los resuelve y no se cuelga nada.
- El barrido `ensure_schema_hooks()` en `BaseConfig.ready()` cubre una
  señal perdida. Es repetible: un segundo barrido devuelve 0.
- Propietario: se excluyen `THIRD_PARTY_MODULE_PREFIXES` (`django.`,
  `rest_framework`), igual que los demás `adopt_*`.
- Resolución de métodos: se cuelga el `classmethod` del `__dict__` del
  mixin, así que `cls` es el modelo adoptante y no el mixin.

## Resultado (2026-11-11T01:51:52)

TASK canónicas: **TASK-API-0515** (`_auto_init`, `_check_removed_columns`)
y **TASK-API-0514** (`_add_sql_constraints`). Esta unidad lleva su contrato
a los modelos que no heredan el cargador.

- Implementación: `adopt_schema_hooks`, su receptor de `class_prepared` y
  `ensure_schema_hooks` en `src/orm/model_classes.py`; el barrido, en
  `BaseConfig.ready()` (`src/addons/base/apps.py`).
- Pruebas (`tests/unit/orm/test_adopt_schema_hooks.py`): rojo por ausencia
  de `SCHEMA_HOOKS`; verde 4/4.
- Anulación 1 (adopción sin efecto): caen exactamente las 3 pruebas que
  dependen de ella.
- Anulación 2 (colgar aunque el modelo ya lo tenga): la primera versión de la
  prueba del `init` propio **no discriminaba**, porque comprobaba que
  `init` estuviera en `vars()`, cosa que también ocurre si lo pisa el
  mixin. Se corrigió para exigir `HrEmployeePublic.init` por `__qualname__`,
  y ahora cae exactamente esa prueba.
- Gate completo sobre el snapshot `8780c994` (`local/adopt-schema-hooks-candidate`):
  **12 699 passed, 0 failed, 6 errors** (el fixture multidb fuera de su base).
  Evidencia: `outputs/gates/full-adopt-8780c994/`. El intento anterior,
  cortado por el reinicio, está en `outputs/gates/full-adopt-interrupted/`
  como interrumpido y sin veredicto.

**Estado contractual:** implementado y verificado por gate completo; **no
aceptado**. Queda pendiente: el ci-multidb de la revisión publicada (alias)
y una prueba de evolución del esquema sobre uno de los 87 (una columna
añadida al modelo sin migración debe detenerse en `_auto_init`). La
presencia de los métodos no prueba por sí sola la equivalencia; la prueba de
`init_models` sobre `res.country` sí ejerce la conciliación.
