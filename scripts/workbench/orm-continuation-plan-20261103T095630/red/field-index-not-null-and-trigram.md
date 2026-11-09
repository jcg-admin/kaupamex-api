# RED — índices btree_not_null y trigram de campos ordinarios

Base 983f06bc. Comando:
`uv run pytest tests/unit/orm/test_field_index_not_null_and_trigram.py -q --reuse-db -p no:cacheprovider -W ignore`

3 failed, 1 passed:

- `btree_not_null`: el editor de esquema sólo emite `CREATE TABLE`; no hay
  `CREATE INDEX … WHERE "code" IS NOT NULL`.
- `trigram`: sólo `CREATE TABLE`; no hay `USING gin ("body" gin_trgm_ops)`.
- portador `test_orm.message.body`: 0 filas en `pg_indexes` (el campo no
  está portado).
- Pasa `index=False` → sin `CREATE INDEX`: es el control negativo, no un RED.

## GREEN

- `orm.fields._add_declared_column_index`, llamada al final de
  `_field_contribute_to_class`: `btree_not_null` → `models.Index(fields=[col],
  condition=Q(col__isnull=False))`; `trigram` → `GinIndex(OpClass(F(col),
  'gin_trgm_ops'))`. Nombre de `orm.fields_company_dependent.declared_index_name`,
  que ahora comparten el índice parcial dependiente de empresa y éste.
- `test_orm.message.body = fields.Text(index='trigram', null=True)` y la
  migración `test_orm/0040_message_body_trigram` (`TrigramExtension` +
  `AddField` + `AddIndex`).
- 4 passed. `makemigrations --check --dry-run`: «No changes detected» — el
  gancho no cambia el índice de ningún otro modelo.

## Controles de anulación

| Anulación | Caen |
|---|---|
| sin la rama `trigram` | 1: trigram |
| sin la rama `btree_not_null` | 1: btree_not_null |
| sin la condición `IS NOT NULL` | 1: btree_not_null |

El portador (`pg_indexes` de `test_orm_message__body_index`) mide la
migración; su control es el RED (0 filas sin ella).

## Admisión de estilo

PASS, después de dos correcciones: la importación de `GinIndex`/`OpClass` va
detrás de la última importación con `# noqa`, porque insertarla antes
desplaza el contexto sintáctico de esas supresiones; y una línea del
docstring pasaba de 79.

## Matriz de impacto

| Eje | Contenido |
|---|---|
| Changed symbols | `orm.fields._add_declared_column_index` (nuevo), `_field_contribute_to_class` (una llamada), `orm.fields_company_dependent.declared_index_name` (extraído de `_not_null_index`), `test_orm.message.body`. |
| Changed behavior | Un campo ordinario con `index='btree_not_null'` o `'trigram'` declara su índice en `Meta`. Nada más: ningún campo de producción lo declara hoy. |
| Direct consumers | `models.Field.contribute_to_class` (todo campo). |
| Indirect consumers | El autodetector de migraciones; el índice parcial dependiente de empresa (mismo nombre). |
| Required contract tests | `tests/unit/orm/test_field_index_not_null_and_trigram.py`. |
| Required regression tests | Archivos que mencionan `company_dependent`, `db_index`, `declared_index_name`, `_not_null_index`, `test_orm.message` o `fields_company_dependent` (33) más `tests/integration/test_orm`. |
| Required integration gates | `makemigrations --check` (hecho). Suite completa y multidb en el corte de publicación: toca `contribute_to_class`, que es transversal. |
| Previously valid evidence | Ninguna: la suite completa en curso es de `983f06bc`, sin este cambio. |
| Uncovered risks | Un campo heredado cuyo `_args__` fusionado traiga `index='btree_not_null'` de un padre: la comprobación de migraciones no detectó ninguno. |

## Regresión de impacto (nivel 2)

En serie (las bases `gw*` las ocupaba la suite de `983f06bc`): 952 passed, 8 xfailed, EXIT=0.
