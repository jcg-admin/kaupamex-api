# Unidad 6f — `_read_grouping_sets`

Autoridad: `odoo19c: odoo/orm/models.py:1598-1859`, odoo-tools
`abe4040ec1a45beee90fb694e4eae4453e46b389`.

## Contrato medido

Varios agrupados en **una** consulta con `GROUPING SETS`; devuelve una lista
por conjunto, en el orden de `grouping_sets`, con tuplas `(grupos…,
agregados…)`.

1. `grouping_sets` vacío → `ValueError`; dominio sin filas → `[[] …]`.
2. Many2many (o propiedad `tags`/`many2many`, o many2one encadenado hacia
   uno) con más de un conjunto puede duplicar filas:
   - con agregados sensibles a la duplicación (cualquiera salvo `max`, `min`,
     `bool_and`, `bool_or`, `array_agg_distinct`, `recordset`,
     `count_distinct`) se descompone por combinaciones de many2many en
     llamadas recursivas y el orden se filtra por conjunto;
   - si sólo `__count` lo es, se sustituye por `id:count_distinct` (también
     en el orden).
3. SQL: `GROUPING(…)` (o `0` sin agrupado) + términos de grupo + agregados;
   `_read_group_orderby` antes de fijar `GROUPING SETS (…)` sin duplicados.
4. Despacho por la máscara de `GROUPING`: el bit de cada expresión, de
   derecha a izquierda; conjuntos con las mismas columnas comparten
   resultado (se copia).
5. Posproceso columna a columna con `_read_group_postprocess_groupby` y
   `_read_group_postprocess_aggregate`.

## Adaptaciones

- `classmethod` sobre el recordset vacío del entorno activo, la misma forma
  que :meth:`_read_group`.
- `get_property_definition` no cuelga de `BaseModel` (medido); la rama de
  propiedades de `might_duplicate_rows` sólo es alcanzable con agrupado por
  propiedades, que espera a la unidad 6e. Se porta verbatim y no se ejercita
  aquí.

## Casos (`tests/unit/orm/test_read_grouping_sets.py`)

1. `[['discussion'], ['discussion', 'priority'], []]` con `__count` y
   `priority:sum` → tres listas coherentes con `_read_group`;
2. conjuntos duplicados por columna → el mismo resultado en las dos;
3. vacío → `ValueError`; dominio sin filas → listas vacías;
4. many2many con `__count` → cuenta distinta por discusión, no por fila
   multiplicada;
5. many2many con `id:sum` → descomposición: el total del conjunto vacío no
   se multiplica por las categorías.

Anulación prevista: retirar la sustitución por `count_distinct` (cae 4) y
retirar la descomposición (cae 5).
