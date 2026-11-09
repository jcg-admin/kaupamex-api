# RED — unidad 6d (`regex_field_agg`, `read_group`)

Revisión base: `feb4a7a9`. Diseño: `designs/read-group-public.md`.

Primer intento: `ImportError: cannot import name 'regex_field_agg'` en la
colección, que tumba los 8 casos a la vez y no discrimina. Se declaró
primero la constante (verbatim, `:112`) y se volvió a medir:

```
uv run --frozen pytest -q --reuse-db -p no:cacheprovider \
    tests/unit/orm/test_read_group_public.py
7 failed, 1 passed, 2 warnings in 7.56s
```

- 7 casos: `AttributeError: ... no attribute 'read_group'`;
- pasa sólo el de `regex_field_agg`, que ya no depende de `read_group`.

## GREEN y anulación

`8 passed`. Controles (bytecode retirado, `cmp` idéntico):

- sin el agregador por defecto del campo: cae exactamente 1 (el lazy por
  many2one, único que pide `priority` sin función);
- sin la llamada a `_read_group_fill_temporal`: cae exactamente 1.

Consumidor corregido en el mismo pase: `AccountInvoiceReport._read_group_select`
afirmaba que `read_group` no existía; ahora nombra la causa real (método de
`BaseModel`, modelo de Django que no lo hereda). Su prueba y el gate de
reclamos de cero: `45 passed`.

## Nivel 2 — `59a8b2e8` (contiene 6a, 6b, 6c y 6d)

`tests/unit tests/integration/test_orm tests/integration/base`, `-n 4`:
`10914 passed, 66 skipped, 4 xfailed in 490.23s`, `EXIT=0`
(boot `3428adc4`). Incluye `tests/unit/scripts`, la lección de `05431171`.
El nivel 3 sigue pendiente.
