# Diseño — contrato diferencial de grupos implicados (`res.groups`)

Fecha: 2026-11-09T02:01:36 · TASK-API-0182 (prioridad ResGroups de 3.2.14).

## Contrato (odoo19c)

- `implied_ids` (`res_groups.py:69`), `all_implied_ids` y
  `all_implied_by_ids` (`:71,76`), calculados como clausura reflexiva
  (`:250,265`) y buscables (`_search_all_implied_ids`, `:245-251`).
- `res.users.all_group_ids = user.group_ids.all_implied_ids`
  (`res_users.py:258,449`).

## Cobertura previa aquí

44 pruebas (`test_res_groups_compute_contract.py`, `test_res_groups_port.py`),
ninguna comparada con la referencia.

## Escenario (`tests/fixtures/reference_res_groups_implied.py` y su espejo)

Cuatro grupos propios: A implica B, B implica C; D aislado. Un usuario en A.

| Escenario | Qué mide |
|---|---|
| `A all_implied` / `C all_implied_by` | clausura reflexiva en los dos sentidos |
| `D all_implied` | grupo aislado: sólo él |
| `user all_group_ids` (entre A-D) | pertenencia efectiva transitiva |
| `search groups implying C` | `_search_all_implied_ids` |
| `search users in C` | búsqueda por `all_group_ids` |
| `after cutting B-C` | la clausura y la pertenencia se recalculan al quitar la arista |

Los valores se comparan por nombre de grupo, ordenados.

## Medido (2026-11-09)

5 de 7 escenarios coinciden: las dos clausuras, el grupo aislado, la
pertenencia efectiva del usuario y su recálculo al cortar la arista B-C.

Los dos de búsqueda levantan `ValueError: Campo inválido
base.ResGroups.all_implied_ids`: `all_implied_ids`, `all_implied_by_ids`
(`res_groups.py:877…`) y `all_group_ids` (`res_users.py:1549`) son
`@property`, no campos; el traductor de dominios no los conoce. Los
`_search_all_*` existen pero con otra firma (`group_ids, negate` → queryset)
y nadie los cablea; sólo los llama `test_res_groups_port.py`.

## Por qué no se cierra en este pase

La forma fiel es la de la referencia: `Many2many` calculado, sin columna,
con `search=` (`res_groups.py:71-78`, `res_users.py:258`). El `Many2many` de
este árbol no admite `store=False` (`orm/fields_relational.py`, docstring de
`Many2many`): un `ManyToManyField` de Django siempre tiene tabla
intermedia. Hace falta construir antes el M2M sin columna —descriptor,
caché, `search` cableado al traductor—, que es una unidad del ORM con su
propio contrato. Queda bajo TASK-API-0485; los dos escenarios van en
`OPEN` del espejo con esta referencia.

## Control de anulación (medido tras la puerta multidb de `f7cbd1fe`)

`all_implied_ids` devolviendo sólo el propio grupo tumba exactamente
`A all_implied` y `after cutting B-C`. `user all_group_ids` no cae: el
usuario calcula su propia clausura (`res_users.py:1549`) en vez de leer
`group_ids.all_implied_ids` como la referencia (`res_users.py:449`). Dos
caminos para el mismo cálculo: se unifican en la unidad del M2M sin columna.
Restaurado con `cmp`.
