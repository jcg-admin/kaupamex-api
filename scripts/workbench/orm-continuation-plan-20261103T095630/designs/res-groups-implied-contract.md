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
