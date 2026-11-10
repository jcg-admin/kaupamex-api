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
