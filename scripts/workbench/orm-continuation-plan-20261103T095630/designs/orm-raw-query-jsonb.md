# TASK-API-0504 — `jsonb` en las consultas crudas del ORM

## Medido (2026-11-09, psycopg 3.3.4, Django 6.0.5, PostgreSQL 16)

Cargadores de la conexión de Django: `json` (oid 114) → `JsonLoader`;
`jsonb` (oid 3802) → `TextLoader`. Lo registra Django en
`django/db/backends/postgresql/psycopg_any.py:61`
(`ctx.register_loader("jsonb", TextLoader)`), para que `JSONField.from_db_value`
decodifique sin doble paso. Sobre un cursor de Django:

| Expresión | Tipo devuelto |
|---|---|
| `'{"a":1}'::jsonb`, `'[1,2]'::jsonb`, `'"x"'::jsonb`, `'3'::jsonb`, `'null'::jsonb` | `str` (texto JSON) |
| `NULL::jsonb` | `None` |
| `'{"a":1}'::json` | `dict` |
| `jsonb -> 'a'` | `str` (`'"b"'`) |
| `jsonb ->> 'a'` | `str` (`'b'`) |

La fuente (`odoo19c: odoo/sql_db.py`) corre sobre psycopg2, que decodifica
`json` y `jsonb` en el cursor; ningún consumidor del ORM de referencia
posprocesa: `_read_group_postprocess_groupby` (`models.py:2248-2275`) y
`get_property_definition` (`:3043-3070`) reciben ya valores de Python.

## Camino compartido

Dos cursores ejecutan el SQL crudo del ORM: `tools.sql.execute_sql` (detrás
de `orm.environments.execute_query` y de `Query`) y
`Environment.execute_query_dict`. Los consumidores de `execute_query` en
`src/orm/models.py` son 10, entre ellos `_fetch_query` (`:9453`), que lee
columnas `jsonb` almacenadas e inserta en caché con `field._insert_cache`.

## Alternativas

1. **Cargador por cursor en el camino del ORM** (elegida). Registrar
   `psycopg.types.json.JsonbLoader` en `cursor.cursor.adapters` de los dos
   cursores del ORM, antes de ejecutar. Es la capacidad del controlador
   (un `AdaptersMap` por cursor) y no toca la conexión: los `QuerySet` de
   Django siguen recibiendo texto y `from_db_value` no decodifica dos
   veces.
2. Cambiar el cargador de la conexión: rompería `JSONField.from_db_value`
   (doble decodificación de un valor que ya es `dict`).
3. Decodificar en cada consumidor (`get_property_definition`, el posproceso
   de `_read_group`): repite el remedio en N sitios, divergente de la
   fuente. Descartada por la directiva.

## Riesgo y control

- Doble decodificación: un consumidor que ya hace `json.loads` sobre el
  resultado crudo. Los de `orm/fields_properties.py` (`:268`, `:570`,
  `:1327`, `:1352`) lo hacen **sólo si** el valor es `str`; se mide con la
  regresión amplia, no se supone.
- Escalares: un `jsonb` que guarda una cadena pasa de `'"x"'` a `'x'`; uno
  numérico, de `'3'` a `3`; `null` JSON pasa a `None` (igual que psycopg2).
- Multibase: el cargador va con el cursor del alias usado; no hay estado
  global.

## Casos (`tests/unit/tools/test_execute_sql_jsonb.py`)

1. `execute_query` decodifica objeto, arreglo, cadena, número, `null` y
   `NULL`;
2. `execute_query_dict` decodifica igual;
3. `json` sigue como `dict` (sin cambio);
4. un cursor de Django ajeno sigue recibiendo texto (sin fuga a la
   conexión);
5. un `JSONField` leído por el `QuerySet` devuelve el valor, no una
   decodificación doble.

Anulación: retirar el registro en `execute_sql` hace caer 1; en
`execute_query_dict`, 2; los 3-5 no dependen de él y deben seguir verdes.

## RED, GREEN y anulación (2026-11-09)

- RED sobre `ae6f4e40`: `2 failed, 3 passed` — caen los dos de
  decodificación; los tres controles (json, cursor ajeno, `JSONField`) ya
  pasaban, como debían.
- Selección por Thyrox: fila `candidates/orm-raw-query-jsonb-0504.jsonl`,
  incorporada con `bin/local_plan supply` (`incorporated:
  orm-raw-query-jsonb-0504`, `skipped: {}`); `bin/task_continuation next`
  la devuelve como frontera. Claims de las tres rutas, `TASK-API-0504`,
  22:50:59Z. Ejecución: manual (sin worker gestionado; ver la auditoría).
- GREEN: `5 passed`. Sin el registro en `execute_sql` cae exactamente 1; sin
  el de `execute_query_dict`, exactamente 1.
- Pendiente antes de aceptar: regresión amplia de consumidores (cambio
  transversal del camino crudo).

## Recuperación de PostgreSQL (2026-11-09 22:48Z)

`Connection refused` en `127.0.0.1:5432`: la consulta no se ejecutó. Causa
comprobada: **reclamo del contenedor** — `boot_id` pasó de `3428adc4` a
`e81170bb` (arranque 22:43:30Z), y el log del cluster dice *"last known up
at 2026-11-09 22:25:50 UTC … not properly shut down"*. La instancia
autorizada es la única del nodo: `pg_lsclusters` → `16 main 5432
/var/lib/postgresql/16/main`. Se recuperó con el procedimiento del
`CLAUDE.md` del repositorio (`sudo pg_ctlcluster 16 main start`), que retiró
el pid obsoleto y ejecutó la recuperación automática; sin bases nuevas, sin
cambiar puerto. Las tres bases residuales siguen intactas.

## Matriz medida por ruta (`outputs/jsonb-paths-2d2eb633.md`, sonda `probes/jsonb_paths.py`)

- psycopg directo **en este proceso** y cursor de Django: `jsonb` → `str`
  en los ocho casos, `json` → `dict`. El cursor directo también, porque el
  `TextLoader` de Django se registra en el contexto global de psycopg al
  importar el backend: no hay cursor «limpio» en el proceso.
- `execute_query` del ORM (con `2d2eb633`): objeto → `dict`, arreglo →
  `list`, cadena → `str` sin comillas, número → `int`, booleano → `bool`,
  `null` JSON → `None`, `NULL` SQL → `None`, `->` → valor decodificado,
  `->>` → texto.
- `JSONField` por `QuerySet`, `Json` y `Properties` por el recordset: `dict`
  (sin decodificación doble). `get_property_definition` → `dict`.

`null` JSON y `NULL` SQL dan los dos `None`, que es también lo que entrega
psycopg2 en la fuente: la conversión no borra una distinción que la
referencia conserve.

## Contrato de la referencia (`odoo-tools@abe4040ec1`, Odoo 19 Community)

- `odoo/sql_db.py` no registra cargador JSON alguno (0 coincidencias de
  `json`): queda el de psycopg2, que decodifica `json` y `jsonb` por
  defecto.
- `odoo/orm/fields_properties.py:143-144`, `:295-296`, `:896-897`, `:919`:
  los consumidores de propiedades decodifican **sólo si** el valor es `str`
  — la misma forma que los de Kaupamex. Por eso la decodificación en el
  cursor no los rompe: es el estado para el que la fuente está escrita.
- `odoo/orm/models.py:2248-2275`: `_read_group_postprocess_groupby` no
  decodifica; el grupo vacío de una propiedad es `_read_group_empty_value`
  → `False` (no es relacional).
