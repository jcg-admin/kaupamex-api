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
