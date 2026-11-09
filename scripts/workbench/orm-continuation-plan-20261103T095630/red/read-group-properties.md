# RED — unidad 6e (`_read_group_groupby_properties`, `_read_group_format_result_properties`)

Revisión base: `9b7cabfc` (con `Properties.type == 'properties'`). Diseño:
`designs/read-group-properties.md`.

Antes de `9b7cabfc` la RED no medía esta unidad: con `type == 'json'` el
agrupado tomaba la rama de ruta many2one (*"Only many2one path is
accepted"*). Medido de nuevo sobre `9b7cabfc`:

```
uv run --frozen pytest -q --reuse-db -p no:cacheprovider \
    tests/unit/orm/test_read_group_properties.py
6 failed
```

Causa única: `NotImplementedError: Grouping by a property waits for
_read_group_groupby_properties (read_group unit 6)`.

## Implementación en borrador — bloqueada por un hueco general, no integrada

El porte verbatim de los dos métodos (con las guardas retiradas) está en
`drafts/read-group-properties-draft.patch` y la prueba en
`drafts/test_read_group_properties.py.txt`. Con él, 1 de 6 pasa (html) y
los otros 5 destapan dos huecos que **no** son de `read_group`:

1. **`get_property_definition` devolvía la definición como texto.** Su
   `execute_query_dict` corre sobre el cursor de Django, que carga `jsonb`
   como texto (lo decodifica después el `from_db_value` de `JSONField`); la
   fuente recibe el `dict` del cursor. Medido: `AttributeError: 'str'
   object has no attribute 'get'`. Afecta también a
   `domains._optimize_properties_date_datetime`, activado por `9b7cabfc`.
2. **Los valores `jsonb` de una consulta cruda llegan como texto JSON.**
   Medido en el agrupado: `'"alpha"'` en vez de `'alpha'`, `'3134'` en vez
   de `3134`, `'"a"'` en vez de `'a'`. La fuente no posprocesa nada en
   `_read_group_postprocess_groupby`: confía en que el cursor de psycopg2
   decodifica `jsonb`.

Además, el comodelo de una propiedad se rechazaba como abstracto: en este
árbol todo modelo concreto hereda `_abstract = True` de `BaseModel`
(divergencia declarada, tarea #329); el borrador lee `_meta.abstract`.

**Sucesor (siguiente unidad, 6e-2):** decodificar `jsonb` en el camino de
consultas crudas del ORM (`execute_query`, `execute_query_dict`) como lo
hace el cursor de la fuente, midiendo antes a sus consumidores: los
`json.loads` condicionales de `orm/fields_properties.py` (`:268`, `:570`,
`:1327`, `:1352`) y cualquier lectura cruda de columnas `jsonb`
traducidas. No se parchea `read_group` ni `get_property_definition` por
separado: el hueco es del cursor. Hasta entonces la rama `properties`
conserva su `NotImplementedError` con nombre.

## Integración sobre `2d2eb633` (TASK-API-0504) — GREEN y anulación

Con la decodificación de `jsonb` en el cursor del ORM, el borrador aplicado
tal cual pasa 3 de 6; los otros 3 fallaban por la **expectativa de la
prueba**, que pedía `None` para el grupo vacío. La fuente da
`_read_group_empty_value` → `False` para un campo no relacional
(`odoo19c: odoo/orm/models.py:2256` y el valor vacío de
`_read_group_empty_value`), y el posproceso convierte el `NULL` en ese
valor: se corrigió la prueba, no el código. `6 passed`.

Para que los controles discriminen se sembró un tercer mensaje con una
categoría borrada y una etiqueta no declarada (escrita en la columna: la
escritura del ORM limpia las etiquetas inválidas). Controles (bytecode
retirado, `cmp` idéntico):

- sin la condición de etiqueta válida (`->>0 = ANY(tags)` → `TRUE`): cae
  exactamente 1 (aparece el grupo `zzz`);
- sin la existencia del many2one (`::int IN (SELECT id …)` → `'x' IS NOT
  NULL`): caen exactamente los 2 de many2one (aparece el id borrado; el
  formateo levanta `DoesNotExist`).
