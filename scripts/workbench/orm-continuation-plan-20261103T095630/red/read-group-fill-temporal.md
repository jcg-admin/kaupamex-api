# RED — unidad 6b (`_read_group_fill_temporal`)

Revisión base: `23c243b9`. Diseño: `designs/read-group-fill-temporal.md`.

```
uv run --frozen pytest -q --reuse-db -p no:cacheprovider \
    tests/unit/orm/test_read_group_fill_temporal.py
9 failed, 2 warnings in 7.89s
```

Causa única en los 9: `AttributeError: 'TestOrmMixed' object has no
attribute '_read_group_fill_temporal'`.

## GREEN y anulación

`9 passed`. Controles (bytecode retirado tras restaurar, `cmp` idéntico):

- sin la unión con `required_dates`: caen 6 de 9 — meses con huecos,
  límites, `min_groups`, segundo `groupby`, zona y semana. Sobreviven el
  campo no temporal, la entrada vacía y el grupo `False` con datos
  contiguos, que no dependen del relleno. El diseño preveía 5; el del
  segundo `groupby` también depende, porque su fila vacía es una rellenada.
- sin el desfase de semana del idioma: cae exactamente 1, el de semana.

Admisión: el primer intento insertaba `import datetime` antes de las dos
importaciones con supresión de `orm/models.py`; la huella de la supresión
incluye su índice en el cuerpo del módulo y el control la rechazó. Las
importaciones nuevas van después.
