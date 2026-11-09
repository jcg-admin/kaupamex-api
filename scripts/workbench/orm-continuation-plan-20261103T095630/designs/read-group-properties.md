# Unidad 6e — `_read_group_groupby_properties` y `_read_group_format_result_properties`

Autoridad: `odoo19c: odoo/orm/models.py:2935-3041` (agrupado) y
`:2638-2744` (formato), odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`.
Prerrequisito: `Environment` como `Mapping` (6e-0, `453c66b8`), porque el
agrupado resuelve el comodelo con `self.env.get(...)`.

## Contrato medido — agrupado

`sql_property = _field_to_sql(alias, 'campo.propiedad', query)`, y por tipo
de la definición (`get_property_definition`):

- `tags`/`many2many`: `LEFT JOIN jsonb_array_elements(...)` sobre un arreglo
  (o `'[]'`), con condición de etiqueta válida (`->>0 = ANY(tags)`) o de
  registro existente en la tabla del comodelo; devuelve el alias;
- `selection`: `LEFT JOIN` con `unnest` de las opciones; una opción que no
  existe agrupa como nula;
- `many2one`: el valor si es número y existe en la tabla del comodelo;
  comodelo inexistente, transitorio o abstracto → `UserError`;
- `date` / `datetime`: conversión del texto JSON;
- `html` → `UserError`;
- resto: `COALESCE(valor, 'false')`.

## Contrato medido — formato

- `selection`: vacío → dominio `= False | not in opciones`;
- `many2one`: `(id, display_name)`; vacío → `= False | not in grupos`;
- `many2many`/`tags`: análogo, con la etiqueta como `(valor, etiqueta,
  color)`;
- `date`/`datetime`: rango, dominio y etiqueta de babel;
- resto: `= valor`.

## Retiro de guardas

Las ramas `properties` de `_read_group_groupby` y
`_read_group_format_result` rehusaban con `NotImplementedError` mientras el
método faltaba. Con el método en `BaseModel` la guarda queda muerta: se
retira y la llamada queda como en la fuente.

## Lo que existe y se reutiliza

`get_property_definition` (en `RecordLoaderMixin`, que los modelos de prueba
heredan vía `TimeStampedModel`), `Properties.property_to_sql`,
`Query.make_alias`/`add_join`, `SQL`, `Domain`, `babel`, `date_utils`.

## Casos (`tests/unit/orm/test_read_group_properties.py`, `test_orm.message`)

1. propiedad `char` → grupos por valor y `False` para el ausente;
2. `selection` con opción inválida → agrupa con los vacíos;
3. `many2one` hacia `test_orm.category` → grupos por id; `read_group` lo
   formatea `(id, display_name)`;
4. `tags` → un grupo por etiqueta válida;
5. `html` → `UserError`;
6. `many2one` con comodelo inexistente → `UserError`.

Anulación prevista: retirar la condición de etiqueta válida (cae 4) y
retirar el `CASE` de existencia del many2one (cae 3).

## Estado (2026-11-09)

Bloqueada por la decodificación de `jsonb` en consultas crudas (ver
`red/read-group-properties.md`). Borrador en `drafts/`; no integrado.
