# RED, GREEN y controles — `_read_group_groupby` (unidad 2 de `read_group`)

Diseño: `designs/read-group-groupby.md`. Referencia: odoo-tools `abe4040ec`,
`odoo/orm/models.py:2015-2119`, `odoo/orm/fields_temporal.py:80-96`.

Comando: `uv run --frozen pytest tests/unit/orm/test_read_group_groupby.py -q --reuse-db -p no:cacheprovider`

- RED: 14 failed (`AttributeError: ... '_read_group_groupby'`).
- GREEN parcial: 12 passed; dos fallos con causa propia:
  - `categories` de `test_orm.discussion` es la relación inversa de Django
    (`ManyToManyRel`): sin `related` ni `relation/column1/column2`. Se usa
    `fields_relational._m2m_relation`, que ya resuelve las dos formas.
  - la zona: el puerto de `property_to_sql` la leía del contexto de proceso;
    la referencia, de `model.env.context`. Se corrige en el mecanismo
    temporal general (`fields_temporal._base_date_property_to_sql`), no en
    `_read_group`.
- GREEN: 14 passed; con las pruebas previas de `property_to_sql`
  (`test_temporal_field_shape.py`, `test_field_to_sql.py`,
  `test_fields_properties.py`): 109 passed.
- Controles de anulación (cae exactamente su caso):
  - zona del proceso en vez de la del recordset → `test_the_zone_comes_from_the_recordset_context`;
  - sin `COALESCE` → `test_a_boolean_groups_nulls_as_false`;
  - sin `::date` → `test_a_date_truncates_and_comes_back_as_date` y `test_a_week_shifts_by_the_first_day_of_the_language`;
  - sin el `LEFT JOIN` de la cadena → `test_a_many2one_path_joins_the_comodel`.
- Admisión de estilo: PASS.

## Adaptaciones declaradas

- `_search` es `classmethod`: `with_context(active_test=False)` y
  `field.context` llegan como su parámetro `active_test`.
- Cadena many2one hacia un comodelo de Django: `NotImplementedError` (no tiene
  `_read_group_groupby` con que seguir). Many2many hacia un comodelo de
  Django: sus filas con sus reglas (`django_comodel_rows`) como subconsulta.
- `properties`: `NotImplementedError` hasta `_read_group_groupby_properties`
  (unidad 6).

## Matriz de impacto

| Eje | Contenido |
|---|---|
| Changed symbols | `BaseModel._read_group_groupby` (nuevo); `fields_temporal._base_date_property_to_sql` (fuente de la zona). |
| Changed behavior | `property_to_sql` de `date`/`datetime` toma la zona del recordset cuando la recibe; sin recordset, igual que antes. |
| Direct consumers | `_read_group` (unidad 5); `property_to_sql` lo usan también `_field_to_sql` de propiedades de fecha y `Properties`. |
| Indirect consumers | Toda expresión `campo.<granularidad>` de un `datetime`. |
| Required contract tests | `test_read_group_groupby.py`. |
| Required regression tests | `tests/unit/orm` (grep de `property_to_sql`, `_read_group`). |
| Required integration gates | Suite completa y multidb en el corte de publicación (ORM espejado). |
| Previously valid evidence | Ninguna. |
| Uncovered risks | Cadenas many2one hacia comodelos de Django y la rama `properties`, declaradas bloqueadas. |

## Regresión de impacto (nivel 2)

Pendiente: se ejecuta cuando el gate de nivel 3 de `6d4c1764` libere las
bases `_gw*` que comparten las ejecuciones `-n 4`.
