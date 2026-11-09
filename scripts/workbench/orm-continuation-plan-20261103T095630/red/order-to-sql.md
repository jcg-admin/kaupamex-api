# RED, GREEN y controles — `_order_to_sql` / `_order_field_to_sql`

Comando: `uv run pytest tests/unit/orm/test_order_to_sql.py -q --reuse-db -p no:cacheprovider -W ignore`

## RED

11 failed: `AttributeError: ... has no attribute '_order_to_sql'` en los
cuatro modelos portadores.

## GREEN

Los dos métodos, verbatim, en `OrderMixin` (`src/orm/models.py`), junto a
`_check_qorder`, que es donde viven sus vecinos en la referencia. Una
adaptación declarada: `env[nombre]` es aquí la clase del modelo, así que el
comodelo al que se delega el orden es `env[nombre]._from_ids(env, (), ())`,
la forma que este árbol ya usa para un recordset vacío.

Dos expectativas de la prueba se corrigieron al medir: con `NULLS LAST` o
`IS NULL` el término no lleva espacio final, así que la coma va pegada, como
produce el `"%s %s %s"` de la fuente con `nulls` no vacío. 11 passed.

## Controles de anulación

| Anulación | Caen |
|---|---|
| sin `reverse` | 2: `reverse` y la delegación del `many2one` en `DESC` (delega con `reverse=True`) |
| sin `COALESCE` | 1: booleano |
| sin la rama `many2one` | 4: delegación, nulos delegados, `x_id.id`, ciclo; sobrevive el comodelo ordenado por `id`, que da la misma salida por la rama general |
| sin la guarda de ciclo | 1: ciclo (recursión) |

Admisión de estilo: PASS.

## Matriz de impacto

| Eje | Contenido |
|---|---|
| Changed symbols | `OrderMixin._order_to_sql`, `OrderMixin._order_field_to_sql` (nuevos). |
| Changed behavior | Ninguno existente: los dos métodos no tienen llamadores en `src/` ni `addons/`. `_search` sigue con `order_to_django`. |
| Direct consumers | Ninguno hoy. Los de la referencia (`_search`, `_read_group`, `_description_sortable`, `override` de addons) son unidades futuras. |
| Indirect consumers | Clases que adoptan `OrderMixin` (`TimeStampedModel`): ganan dos métodos. |
| Required contract tests | `tests/unit/orm/test_order_to_sql.py`. |
| Required regression tests | `tests/unit/{orm,base}`, `tests/integration/{base,crm,test_orm}` (grep de `_check_qorder`, `order_to_django`, `OrderMixin`, `regex_order`). |
| Required integration gates | Suite completa y multidb en el corte de publicación. |
| Previously valid evidence | Ninguna para esta revisión. |
| Uncovered risks | Una subclase que ya definiera un atributo `_order_to_sql`: grep → 0. |

## Regresión de impacto (nivel 2)

`-n 4`: 5566 passed, 65 skipped, 4 xfailed, EXIT=0.
