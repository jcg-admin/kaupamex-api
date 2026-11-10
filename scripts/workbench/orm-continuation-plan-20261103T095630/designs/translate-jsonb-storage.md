# TASK-GEN-0060 — Almacenamiento `jsonb` de `translate=True` y los tres métodos

Fecha: 2026-11-10. Referencia: odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`. TASK canónica: **TASK-GEN-0060**
(`pending`, bloquea a `#400`); eje del campo: **TASK-GEN-0436** (*hermano de
company_dependent*). Relacionadas: TASK-API-0283 (`field_description` sin
`translate=`), TASK-API-0375 y TASK-GEN-0062 (catálogo `.po`, otra
obligación).

## Contrato reconstruido

| Aspecto | Referencia | Cita |
|---|---|---|
| Columna | `jsonb` cuando `translate` o `company_dependent` | `odoo19c: odoo/orm/fields.py:783` |
| Inserción | `{'en_US': v, lang: v}` | `fields_textual.py:87-92` |
| Actualización | `UPDATE` con `COALESCE(col, {'en_US': primer valor}) || nuevo`; conserva los demás idiomas | `models.py:4564-4576` (`_write_multi`) |
| Idioma de lectura | `env.lang or 'en_US'` (traducción completa); `env._lang` para términos | `fields_textual.py:213-214` |
| Respaldo | `lang → en_US` (y `_lang → lang → _en_US → en_US` en edición) | `:216-224` |
| Caché | `LangProxyDict` por idioma; `prefetch_langs` trae todos los instalados | `:226-260` |
| Copia | `copy_translations` recorre los campos traducibles almacenados | `models.py:5465-5528` |
| `update_field_translations` | `{lang: str|False}`; `False` retira el idioma y cae al `en_US` | `models.py:3492-3584` |
| `get_field_translations` | lista `{lang, source, value}` por idioma instalado; contexto `translation_type`, `translation_show_source` | `:3664-3703` |
| Términos | `translate` invocable: diccionario por término, `get_translation_dictionary` | `fields_textual.py:171-196`, `models.py:3619-3656` |

## Estado de este árbol

- 14 campos `translate=True`, todos `CharField` sobre `varchar`, 12 tablas,
  7 apps (`outputs/translate-fields.tsv`, sonda sobre la base migrada).
  Ninguno con traducción por términos.
- `translate=True` sólo se anota (`src/orm/fields_textual.py:204-276`).
- `Environment.lang` (`environments.py:1129`) y `_lang` (`:1239`) existen;
  `res.lang.get_installed` (`res_lang.py:221`) existe.
- `_write_rows` (TASK-API-0510) es la escritura física única: la rama
  `translate` de la expresión SQL de la fuente cae ahí.

## Mecanismo a extender (sin capa paralela)

El eje `company_dependent` (`src/orm/fields_company_dependent.py`) ya es una
columna `jsonb` con clave, despacho por tipo base, lectura del valor de la
clave activa con respaldo (`value_for_current_company`,
`get_company_dependent_fallback_sql` con `COALESCE`) y escritura de una
clave (`set_for_company`). La traducción es el mismo patrón con la clave
`lang`: se generaliza ese despachador para una segunda clave, en lugar de
crear un campo de traducciones aparte.

## Migración segura de las 14 columnas

1. Inventario congelado: `outputs/translate-fields.tsv`, copiado al
   Workbench antes de migrar.
2. Por app, una migración con `AlterField` a la columna `jsonb` y
   `RunSQL` explícito: `ALTER COLUMN c TYPE jsonb USING CASE WHEN c IS NULL
   THEN NULL ELSE jsonb_build_object('en_US', c) END`; reversa
   `USING c->>'en_US'`. El valor actual queda bajo `en_US`, que es el
   idioma base de la referencia.
3. Respaldo: `pg_dump --table` de las 12 tablas antes de aplicar en una
   base con datos; en pruebas, las filas sembradas comparan antes/después.
4. Índices sobre columnas traducibles: medir los que existan antes de
   convertir (un `btree` sobre `varchar` no sirve a `jsonb`).

## Pruebas de preservación y de contrato (RED previstas)

1. Migración sobre filas existentes: `'Kg'` → `{'en_US': 'Kg'}`; `NULL`
   sigue `NULL`; la reversa devuelve el texto.
2. Lectura con `lang='es_MX'` sin traducción → valor `en_US`.
3. `update_field_translations({'es_MX': 'Kilo'})` conserva `en_US`.
4. `update_field_translations({'es_MX': False})` retira `es_MX` y cae al
   `en_US`.
5. Escritura con `lang='es_MX'` toca sólo esa clave (rama `translate` de
   `_write_rows`).
6. Búsqueda `ilike` por el idioma activo con respaldo.
7. `copy()` copia todas las traducciones.
8. `get_field_translations` devuelve un elemento por idioma instalado.

## Dependencias

- Ninguna de esquema: la autoridad son las migraciones (TASK-API-0515 vigila
  la sincronía).
- `_write_rows` (TASK-API-0510) recibe la rama de escritura por idioma.
- `copy_translations` (`models.py`) y `field_description` de `ir.model.fields`
  (TASK-API-0283) son los primeros consumidores.

Lo que este diseño no cierra: la implementación. Es una unidad amplia —campo,
caché por idioma, lectura y búsqueda por idioma, migración de 14 columnas— y
se ejecuta como TASK-GEN-0060 con estas pruebas como RED.

## Implementación — decisiones medidas (2026-11-10)

Mediciones previas, sobre la base de pruebas migrada (`orm_x2hokp_qa`):

- Ninguna de las 14 columnas tiene índice ni restricción `UNIQUE`/`CHECK`
  propia (`pg_indexes`, `pg_constraint`); la conversión no tiene objetos que
  rehacer. Filas con datos: sólo `hr_departure_reason.name` (3, sembradas
  por migración de datos).
- Consumidores Django por valor (`.filter(<campo>=…)`) en código de
  producto: cero en los 14 campos. Las pruebas se miden con la regresión.
- `tools.sql.convert_column_translatable` ya está portado
  (`src/tools/sql.py:668`) con el `USING` de la fuente; la migración lo usa,
  no copia el SQL.
- `models.Field._convert_db_column` (`orm/fields.py`) no tiene la rama de
  `BaseString` (`odoo19c: fields_textual.py:64-68`); se añade, y la
  operación de migración llama al método del campo, de modo que la única
  autoridad de esquema siguen siendo las migraciones y el SQL sale del ORM.
- Búsqueda: `_search` compila por `Domain._to_sql` → `Field.condition_to_sql`
  → `Field.to_sql`; ahí entra la rama `translate` de la fuente
  (`fields_textual.py:394-402`, `COALESCE(col->>lang, col->>'en_US')`).

Forma del campo — el patrón de `CompanyDependent`, con la clave `lang`:

| Pieza | Decisión |
|---|---|
| Clase | `TranslatedChar(models.JSONField)` en `orm/fields_textual.py` (la fuente lo tiene en `BaseString`; no hay archivo nuevo), `type = 'char'` |
| Despacho | `fields.Char(translate=True)` la devuelve, como `company_dependent=True` devuelve `CompanyDependent` |
| `attname` | `<campo>_translations` guarda el mapa; la columna conserva el nombre del campo |
| Descriptor sobre `name` | lee `translation_lang` con respaldo `get_translation_fallback_langs`; escribe la clave del idioma; `None`/`False` vacía la columna |
| Alta | `{'en_US': v, lang: v}` (`convert_to_column_insert`, `:84-91`) |
| Escritura | `{**mapa, lang: v}`; si `en_US` no está activo, también `en_US` (`:317-325`) |
| Tamaño | `s[:size]` (`convert_to_cache`, `:101-115`) |
| Consultas Django | `get_lookup` envuelve el lado izquierdo con el texto del idioma con respaldo, para que `.filter(name='Kg')` compare texto; sin esto la comparación `jsonb = '"Kg"'` no da error y no casa nada |
| `to_sql` | rama `translate` de la fuente |
| Migración | `SeparateDatabaseAndState`: estado `AlterField`, base `ConvertColumnTranslatable` (`migration_operations.py`), reversible |
| Métodos | `get_field_translations`, `update_field_translations`, `_update_field_translations` en `BaseModel`; `_get_stored_translations` en el campo; la rama de traducción de los dos `copy_translations` |

Fuera de esta unidad, declarado: términos (`translate` invocable) — ningún
campo del árbol lo declara; `prefetch_langs`/`LangProxyDict` en la caché del
ORM — el descriptor resuelve el idioma sobre el mapa de la fila, como hace
`CompanyDependent` con la empresa; la caché por idioma de la fuente queda
como divergencia de mecanismo y su clase ya existe sin consumidor.

## RED, GREEN, regresión y anulación (2026-11-10)

- RED (`tests/unit/orm/test_translated_char.py`, sobre `afeecc89`):
  `13 failed`, cada uno por su causa prevista (columna `varchar`, sin
  `update_field_translations`, operador `->>` inexistente sobre `varchar`).
- Defecto del primer diseño, medido: la conversión dentro de
  `SeparateDatabaseAndState` no hacía nada. Cada operación de base recibe el
  estado viejo más su propio `state_forwards`, así que veía el `CharField`
  y salía antes de convertir; la migración quedaba aplicada y la columna en
  `varchar`. `ConvertColumnTranslatable` es ahora un `AlterField` que
  convierte por el campo de destino.
- Migración aplicada sobre la base de pruebas: las 14 columnas son `jsonb`;
  las 3 filas sembradas quedan `{"en_US": <texto>}`. La reversa se prueba
  en `test_conversion_round_trips_the_text`.
- Regresión derivada (17 directorios): `8 failed, 9367 passed`. Siete
  causas: tres pruebas que afirmaban el estado anterior (los símbolos no
  existían; la bandera no cambiaba el almacenamiento; un reclamo de cero en
  `web/models/models.py`), dos que leían `max_length`/`values_list` como si
  la columna fuera `varchar`, y un defecto real: `QuerySet.update(campo=str)`
  rechazaba el texto. Se cierra con la fusión de `_write_multi`
  (`COALESCE(col, {'en_US': v}) || {idioma: v}`) en `get_db_prep_save`.
- GREEN: `14 passed`; las siete del derivado, verdes.
- Anulación, cada una restaurada y verificada con `cmp`, `__pycache__`
  retirado: sin los lookups de texto → cae sólo el filtro Django; sin la
  rama de `to_sql` → sólo `to_sql`; sin respaldo → sólo la lectura con
  respaldo; sin `en_US` en el alta → sólo el alta; `False` como `''` → sólo
  la retirada del idioma; sin la rama de copia → sólo la copia; sin la
  fusión del `UPDATE` → la prueba del `UPDATE` y las tres de
  `base_sparse_field` que escriben por esa vía.

Divergencias declaradas en el código: `values()`/`values_list()` entregan el
mapa guardado (la columna), no el texto del idioma; el `ORDER BY` de Django
sobre el campo ordena `jsonb` — el orden del ORM pasa por `to_sql`; los
términos (`translate` invocable) y la caché por idioma de la fuente no se
portan.
