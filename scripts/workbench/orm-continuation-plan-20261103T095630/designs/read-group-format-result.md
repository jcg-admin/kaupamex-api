# Unidad 6c — `READ_GROUP_DISPLAY_FORMAT` y `_read_group_format_result`

Autoridad: `odoo19c: odoo/orm/models.py:315-333` (`READ_GROUP_DISPLAY_FORMAT`)
y `:2554-2638` (`_read_group_format_result`), odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`.

## Contrato medido

Por cada `group` de `lazy_groupby` y cada fila:

- recordset → `(id, sudo().display_name)` o `False`; el dominio usa el id;
- many2many sin valor → `(campo, 'not any', [])`; si no, `(campo, '=', valor)`;
- `date`/`datetime` con granularidad de tiempo y valor fecha:
  - etiqueta con `babel.dates.format_date`/`format_datetime` y
    `READ_GROUP_DISPLAY_FORMAT[granularidad]` en la locale de `get_lang`;
  - `datetime` con `tz` válida: inicio y fin localizados y llevados a UTC
    (cada uno por separado, para respetar un cambio de horario entre los dos);
  - semana: `W{semana} {año:04}` con `date_utils.weeknumber`;
  - `__range[group] = {'from', 'to'}` en formato de servidor y dominio
    `['&', (campo, '>=', from), (campo, '<', to)]`;
- granularidad numérica con valor no nulo → `(f"{campo}.{granularidad}", '=', valor)`;
- fecha sin valor → `__range[group] = False`;
- `properties` → `_read_group_format_result_properties` (y `continue`);
- `row['__domain'] &= Domain(additional_domain)`; al final cada
  `__domain` se convierte en lista.

## Lo que ya existe y se reutiliza

`tools.date_utils.weeknumber`, `tools.misc.DEFAULT_SERVER_DATE(TIME)_FORMAT`,
`get_lang`, `READ_GROUP_TIME_GRANULARITY`/`READ_GROUP_NUMBER_GRANULARITY`,
`orm.domains.Domain`, `babel` 2.18.0 (dependencia instalada).

## Lo que queda fuera de esta unidad, con su condición

`_read_group_format_result_properties`: depende de
`get_property_definition`, que hoy cuelga de `RecordLoaderMixin` y **no** de
`BaseModel` (medido: `hasattr(BaseModel, 'get_property_definition')` →
`False`), y sólo es alcanzable cuando el agrupado por propiedades exista
(`_read_group_groupby_properties`). Entra con esa unidad (6e). Hasta
entonces la rama `properties` llama al método si existe y, si no, rehúsa
con `NotImplementedError` que nombra la unidad — la misma forma que la
rama `properties` de `_read_group_groupby`.

## Fachada

`READ_GROUP_DISPLAY_FORMAT` deja de estar bloqueado: se liga en
`src/models/__init__.py` y sale de `BLOCKED_BY_ITS_SYMBOL` de
`tests/unit/orm/test_sugar_packages.py`, cuyo control positivo se pone rojo
en cuanto `src/orm` lo declara.

## Casos (`tests/unit/orm/test_read_group_format_result.py`)

1. many2one → `(id, display_name)` y dominio por id;
2. many2one vacío → `False`;
3. many2many vacío → `not any`;
4. fecha por mes → etiqueta `November 2026`, `__range`, dominio de rango;
5. fecha por semana → `W45 2026`;
6. `datetime` por día con zona → `__range` en UTC;
7. fecha vacía → `__range` `False`;
8. granularidad numérica → dominio `campo.granularidad`;
9. la constante se re-exporta en `models` y su bloqueo caduca.

Anulación prevista: retirar la conversión del recordset (caen 1, 2);
retirar el `astimezone(pytz.utc)` (cae 6).
