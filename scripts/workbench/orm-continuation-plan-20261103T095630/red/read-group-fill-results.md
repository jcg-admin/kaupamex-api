# RED — unidad 6a (`_read_group_expand_full`, `_read_group_fill_results`)

Revisión base: `318e06a1`. Diseño: `designs/read-group-fill-results.md`.

```
uv run --frozen pytest -q --reuse-db -p no:cacheprovider \
    tests/unit/orm/test_read_group_fill_results.py
8 failed, 2 warnings in 6.89s
```

Causas (las esperadas, una por caso):

- 6 casos: `AttributeError: 'TestOrmMessage' object has no attribute
  '_read_group_fill_results'`;
- 1 caso: `... no attribute '_read_group_expand_full'`;
- 1 caso: `assert True == <bound method SelectionField._default_group_expand>`
  — `group_expand=True` no se mapea al expansor por defecto.
