# RED, GREEN y control — dominio de cada One2many sobre registros de new()

Base `2ce0f88e`. Comando:
`uv run pytest tests/unit/orm/test_one2many_domain_on_new_records.py -q --reuse-db -p no:cacheprovider -W ignore`

## RED

2 failed, 1 passed. Causa: `important_messages` de un dueño nuevo devuelve
la línea no importante (`assert (<NewId>,) == ()`), porque lee la caché de la
relación inversa sin dominio. Pasa el caso de la línea importante, que está
en los tres campos con o sin filtro.

## GREEN

`One2many.__get__`, rama de `NewId`: `lines.filtered_domain(domain)` con
`self.get_comodel_domain(instance)`. Con las unidades vecinas
(`test_one2many_on_new_records.py`, `test_many2one_write_inverses.py`):
7 passed.

## Control de anulación

Sin el filtro (`return lines`): caen exactamente los 2 casos del RED; el de la
línea importante sobrevive, que es lo esperado porque no depende del filtro.
Restaurado desde la copia; `git diff --stat` mostró sólo las 8 líneas del
cambio.

Admisión de estilo sobre el índice: PASS.

## Regresión de impacto

Subconjunto derivado (`grep -rlE "One2many|\.new\(" --include=*.py tests/`, 14 directorios de suite): `-n 4` → 8114 passed, 66 skipped, 4 xfailed, EXIT=0.
