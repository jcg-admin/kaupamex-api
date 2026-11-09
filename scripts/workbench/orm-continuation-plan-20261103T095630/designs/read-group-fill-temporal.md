# Unidad 6b — `_read_group_fill_temporal`

Autoridad: `odoo19c: odoo/orm/models.py:2387-2552` (odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`).

## Contrato medido en la referencia

1. Sólo actúa si el primer `groupby` es `date`/`datetime`, o `properties` con
   `:`; si no, devuelve `data` tal cual.
2. Granularidad: la del spec, `month` por omisión. Con `week`, el desfase
   de días sale de `get_lang(env).week_start` (medido aquí: `en_US`, `'7'`
   → desfase 1, la semana empieza en domingo).
3. Intervalo: `READ_GROUP_TIME_GRANULARITY[granularidad]`.
4. Zona: sólo para `datetime` y si `context['tz']` está en
   `pytz.all_timezones_set`; localiza los límites `fill_from`/`fill_to`.
5. Límites: los dados (al inicio de la granularidad, menos el desfase), o
   los grupos existentes primero/último (se supone `data` ordenada); si
   falta uno se copia el otro; sin ninguno, devuelve `data`.
6. `min_groups > 0` extiende `fill_to` a `fill_from + (min_groups-1)*intervalo`;
   `fill_to < fill_from` devuelve `data`.
7. Fechas requeridas: `date_utils.date_range(fill_from, fill_to, intervalo)`,
   unidas con las existentes y ordenadas.
8. Elemento vacío: `_read_group_empty_value` por agregado **y** por cada
   `groupby[1:]`.
9. Salida: por cada fecha, sus filas o un vacío; al final, las filas cuyo
   valor de grupo es `False`.

## Piezas que ya existen en Kaupamex (se reutilizan, no se reimplementan)

`tools.date_utils.start_of` y `date_range`, `orm.utils.READ_GROUP_TIME_GRANULARITY`,
`tools.misc.get_lang`, `orm.fields_temporal.Date`/`Datetime`,
`BaseModel._read_group_empty_value` (unidad 4).

## Adaptaciones

Ninguna de conducta. Importaciones nuevas de la biblioteca estándar y de
`pytz`/`tools.date_utils` en `orm/models.py`, que la referencia también
importa.

## Casos (`tests/unit/orm/test_read_group_fill_temporal.py`, `test_orm.mixed`)

1. campo no temporal → `data` intacta;
2. meses con huecos (jun, sep) → jun..sep con vacíos;
3. `fill_from`/`fill_to` (ago..oct) con datos en sep → ago, sep, oct;
4. `min_groups=4` desde ago → ago..nov;
5. sin datos ni límites → `[]`;
6. la fila con grupo `False` va al final;
7. el segundo `groupby` recibe su valor vacío en las filas rellenadas;
8. `datetime` con `tz` válida → límites localizados;
9. `week` en `en_US` → semanas que empiezan en domingo.

Control de anulación previsto: retirar la unión con `required_dates`
(caen 2, 3, 4, 8, 9) y retirar el desfase de semana (cae 9).

*Métrica:* listas devueltas sobre datos construidos en la prueba.
*Ciega a:* el agrupado por `properties` (sin modelo de prueba con
propiedades fechadas en esta unidad) y el consumo desde `read_group`.
