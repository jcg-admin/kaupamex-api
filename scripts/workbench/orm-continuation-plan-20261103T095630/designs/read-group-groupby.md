# Diseño — unidad 2 de `read_group`: `_read_group_groupby`

Referencia: odoo-tools `abe4040ec`, `odoo/orm/models.py:2015-2119`
(`_read_group_groupby`) y `odoo/orm/fields_temporal.py:80-96`
(`BaseDate.property_to_sql`). Depende de `_search` → `Query`
(`designs/search-returns-query.md`).

## Contrato

`_read_group_groupby(alias, groupby_spec, query) -> SQL`, ramas en el orden de
la fuente:

1. campo inexistente → `ValueError`;
2. `properties` → `_read_group_groupby_properties` (unidad 6: hasta entonces la
   rama se declara bloqueada, nunca se omite en silencio);
3. cadena `m2o.campo` → `comodel.with_context(active_test=False)._search([])`;
   alias `campo` o `campo__<uid>` si el `Query` del comodelo lleva `WHERE` y no
   hay elevación; `LEFT JOIN` a la tabla o al `subselect` del comodelo; y se
   delega en `comodel._read_group_groupby` con el alias nuevo;
4. granularidad sobre un campo no temporal → `ValueError`;
5. `many2many` (también un `related` no almacenado que se recorre): `LEFT JOIN`
   a la tabla de relación con `alias.id = rel.column1` y, si el `Query` del
   comodelo filtra, `AND rel.column2 IN (subselect)`; devuelve `rel.column2`;
6. resto → `_field_to_sql`.

Después, para `date`/`datetime`: granularidad obligatoria y válida; las
numéricas pasan por `property_to_sql` (`date_part`); `datetime` fija la zona
con `property_to_sql(…, 'tz', …)`; `week` desplaza por `week_start` del idioma;
las de `READ_GROUP_TIME_GRANULARITY` usan `date_trunc`; un `date` vuelve a
`::date`. Un `boolean` se agrupa con `COALESCE(…, FALSE)`.

## Lo que ya existe en Kaupamex (medido) y lo que falta

- `Date`/`Datetime.property_to_sql` **ya existe**: `_base_date_property_to_sql`
  (`src/orm/fields_temporal.py:157-189`), instalado en `DateField` y
  `DateTimeField` (`:451-455`), con pruebas en
  `tests/unit/orm/test_temporal_field_shape.py`, `test_field_to_sql.py` y
  `test_fields_properties.py`. La primera versión de este diseño decía que
  faltaba: se buscó el método sólo en `fields_properties.py`. **No se
  reimplementa.**
- Divergencia declarada en ese puerto: lee la zona de `get_context()` (contexto
  de proceso) y no de `model.env.context`. Desde que `_search` pasa un recordset
  con su `env`, hay que medir si los dos coinciden dentro de `Environment(...)`
  con `tz` en el contexto; si no, el puerto pasa a leer `model.env.context`
  cuando recibe un recordset. Prueba discriminante: agrupar `datetime` con
  `tz` en el contexto del entorno y sin `tz` en el de proceso.
- `date_trunc` (`READ_GROUP_TIME_GRANULARITY`), el desplazamiento de `week` y
  el `::date` son de `_read_group_groupby` mismo: se portan con él.
- `get_lang(env).week_start`: existe (`tools.misc.get_lang`, campo
  `week_start` de `res.lang`).
- `READ_GROUP_*_GRANULARITY`: existen en `orm/utils.py`.
- `Many2many.relation/column1/column2`: los declara el campo
  (`fields_relational.py:757-800`).

## Pruebas (RED)

`tests/unit/orm/test_read_group_groupby.py`: el `SQL` de cada rama sobre
`test_orm.message`/`discussion` (campo simple, booleano, cadena many2one con y
sin reglas, many2many con y sin dominio del comodelo, fecha con cada
granularidad, `week` con `week_start`, `datetime` con `tz`), y los `ValueError`.

### Medido: la fuente de la zona (2026-11-09)

Con `Environment(None, SUPERUSER_ID, {'tz': 'America/Mexico_City'})` activo,
`get_context()['tz']` y `env.context['tz']` coinciden; un `Environment` anidado
sin `tz` los deja a los dos en `None`. **Se separan** cuando un recordset lleva
otro contexto sin que su entorno sea el activo: `Model.with_context(tz=…)`
devuelve un recordset cuyo `env.context` tiene la zona y el contexto de proceso
no. La referencia agrupa con la zona del recordset (`model.env.context`); el
puerto actual, con la del proceso. RED de la unidad 2: agrupar un `datetime`
por `hour_number` con `Model.with_context(tz='America/Mexico_City')` fuera de
un entorno con `tz`.
