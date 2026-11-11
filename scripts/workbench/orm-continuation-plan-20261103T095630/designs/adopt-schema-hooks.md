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
