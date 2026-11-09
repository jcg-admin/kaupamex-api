# RED — unidad 6c (`READ_GROUP_DISPLAY_FORMAT`, `_read_group_format_result`)

Revisión base: `05431171`. Diseño: `designs/read-group-format-result.md`.

```
uv run --frozen pytest -q --reuse-db -p no:cacheprovider \
    tests/unit/orm/test_read_group_format_result.py
9 failed, 2 warnings in 6.94s
```

- 8 casos: `AttributeError: ... no attribute '_read_group_format_result'`;
- 1 caso: `AttributeError: module 'models' has no attribute
  'READ_GROUP_DISPLAY_FORMAT'`.

## GREEN y anulación

`9 passed` (más `test_sugar_packages.py`: su control positivo del bloqueo
de `READ_GROUP_DISPLAY_FORMAT` se puso rojo al declararse la constante, como
debía; la constante pasó a `PORTABLE_NOW` y a la fachada `models`).

- sin convertir el recordset en `(id, display_name)`: caen exactamente 2
  (many2one con valor y vacío);
- sin `astimezone(pytz.utc)`: cae exactamente 1 (rango de `datetime`).
