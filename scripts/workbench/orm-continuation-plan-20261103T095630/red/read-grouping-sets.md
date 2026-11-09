# RED — unidad 6f (`_read_grouping_sets`)

Revisión base: `59a8b2e8`. Diseño: `designs/read-grouping-sets.md`.

```
uv run --frozen pytest -q --reuse-db -p no:cacheprovider \
    tests/unit/orm/test_read_grouping_sets.py
6 failed, 2 warnings in 7.97s
```

Causa única: `AttributeError: type object '…' has no attribute
'_read_grouping_sets'`.

## GREEN y anulación

`6 passed`. Controles (bytecode retirado, `cmp` idéntico):

- sin sustituir `__count` por `id:count_distinct`: cae exactamente 1 (la
  cuenta por many2many del conjunto vacío sale 3 en vez de 2);
- sin la descomposición recursiva: cae exactamente 1 (la suma del conjunto
  vacío se multiplica por las categorías).
