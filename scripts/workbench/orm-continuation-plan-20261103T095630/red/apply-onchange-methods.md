# RED — BaseModel._apply_onchange_methods

Revisión base: b9430f51. Comando:
`uv run pytest tests/unit/orm/test_apply_onchange_methods.py -q --reuse-db -p no:cacheprovider -W ignore`

Resultado: 7 failed, 1 passed.

- Los 7 fallos: `AttributeError: 'TestOrmCategory' object has no attribute '_apply_onchange_methods'`.
  Es la causa declarada: el método no existe en `BaseModel`.
- Pasa `test_the_discussion_registers_its_three_onchange_fields`: el registro
  (`orm.registry.onchange_methods`) ya cumplía su parte del contrato; la prueba
  queda como evidencia de esa parte, no como RED.

## GREEN

Tras añadir `BaseModel._apply_onchange_methods` y `apply_onchange_methods`
(`src/orm/models.py`) y llevar `Base.onchange` de `web` a esa función:
`tests/unit/orm/test_apply_onchange_methods.py` +
`tests/unit/web/test_models_onchange.py` → 27 passed.

## Controles de anulación (sobre los mismos dos archivos)

| Anulación | Caen |
|---|---|
| C1 `return` al inicio de `apply_onchange_methods` | 4 de ORM (selección, exclusión, aviso, error) + 4 de web (aviso, valor, dos avisos, segunda pasada) — 8 |
| C2 sin la condición de `excluded_methods` | 1: `test_excluded_methods_are_skipped` |
| C3 sin `has_field(key)` | 3: las tres pruebas que pasan por `_onchange_name_value` (la clave `unknown` revienta en `__setitem__`) |
| C4 sin `key != 'id'` | 2: `test_value_skips_id_and_unknown_keys` (`assert not 99`) y `test_excluded_methods_are_skipped` |

Las pruebas de retorno falso y de campo sin onchange pasan con C1: miden una
ausencia; su contraparte positiva es `test_only_the_methods_of_the_changed_field_run`,
que sí cae. Se restauró `src/orm/models.py` desde la copia y se comprobó con
`git diff --stat` (49 inserciones, las del cambio).

Divergencia de texto declarada: el título por defecto de un aviso en `web`
pasa de `_('Aviso')` a `_("Warning")`, el literal de la referencia; ninguna
prueba de `web` lo afirma.

## Regresión de impacto

Subconjunto derivado con
`grep -rlE "onchange|_onchange_methods" --include=*.py tests/ | sed 's|/[^/]*$||' | sort | uniq -c`
(10 directorios; `tests/fixtures` no es suite): `-n 4` → 6350 passed, 65 skipped, EXIT=0.

## Corrección de forma en `web` (admisión de estilo)

La primera forma reescribía el bucle de `Base.onchange`. La admisión la rechazó:
7 violaciones heredadas de `addons/web/models/models.py` (comentarios y
decoradores cuyo nodo mínimo es `class Base`) cambian de huella cuando cambia
el cuerpo de la clase (`syntax_context` de `scripts/check_python_style_increment.py`).
Forma final: `Base` no se toca; `_apply_onchange_method` queda como adaptador
de una línea sobre `orm.models.apply_onchange_methods`: pasa `(method,)`,
convierte la lista de avisos a `OrderedSet` y la reescribe en ese orden. El
contrato sigue teniendo una sola implementación. Las importaciones se fusionan
en las existentes (`from orm import models as orm_models, registry`,
`from tools import date_utils, misc`) para no añadir sentencias.

Repetidos sobre la forma final: GREEN 27 passed; C1 8 fallos (los mismos);
C2 1 fallo (el mismo). Admisión: PASS.

Regresión de impacto sobre la forma final (mismo subconjunto, `-n 4`): 6350 passed, 65 skipped, EXIT=0.
