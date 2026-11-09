# RED — porte completo de tools/sql.py

Base bea56804. Comando:
`uv run pytest tests/unit/tools/test_sql_reference_shape.py -q -p no:cacheprovider -W ignore`

5 failed, cada uno por su divergencia:

| Prueba | Causa |
|---|---|
| `test_all_matches_the_reference` | `AttributeError: module 'tools.sql' has no attribute '__all__'` |
| `test_sql_slots_match_the_reference` | sobra `'__output_field'` |
| `test_sql_init_signature_matches_the_reference` | `('output_field', 'KEYWORD_ONLY')` de más |
| `test_sql_class_annotations_match_the_reference` | `[] == ['__code', '__params', '__to_flush']` |
| `test_order_by_type_matches_the_reference_with_its_default` | `KeyError: 'no_such_type'` (dict llano, sin el defecto 16) |

## Ejecución en worktree inmutable

RED, GREEN, controles y regresión se ejecutaron en un worktree desacoplado
(`git worktree add --detach`) con el entorno virtual del clon, mientras
multidb usaba el checkout de trabajo. El parche se trasladó después con
`git apply` sin cambios.

## RED funcional (código anterior, mismas pruebas)

8 failed: las 5 de forma y las 3 funcionales nuevas de `test_sql.py`
(`test_an_unknown_column_type_orders_last_and_joins_the_map`,
`test_output_field_is_an_ordinary_unused_name_as_in_the_reference`,
`test_stock_quant_builds_its_django_expression_with_rawsql`).

## GREEN

`test_sql_reference_shape.py`, `test_sql.py`, `test_sql_column_schema.py`,
`test_sql_schema_helpers.py`, `test_field_conversion.py`: 103 passed.

Corrección de la prueba durante el GREEN: Python transforma el nombre de las
anotaciones privadas de clase (`__code` → `_SQL__code`), en la referencia
igual que aquí. La prueba aplica esa transformación a los nombres del AST; no
lleva ninguna lista propia.

## Controles de anulación

| Anulación | Caen |
|---|---|
| `output_field=None` de vuelta en la firma | 1: firma |
| sin `__all__` | 1: `__all__` |
| `dict` llano en vez de `defaultdict` | 2: tabla y la funcional del tipo desconocido |

## Admisión de estilo

PASS. Las dos violaciones heredadas de `stock_quant.py` (líneas 856 y 860),
cuya sentencia contenedora cambió, se corrigieron en el tramo de la unidad.

## Regresión de impacto (nivel 2)

Directorios de la matriz: `-n 4` → 7631 passed, 39 skipped, 4 xfailed, EXIT=0.
