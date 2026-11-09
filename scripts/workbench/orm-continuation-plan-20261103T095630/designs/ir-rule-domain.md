# Diseño — `ir.rule` devuelve `Domain` (paso 1 de `search-contract-analysis.md`)

Referencia: odoo-tools `abe4040ec`, `odoo/addons/base/models/ir_rule.py:141-173`
(`_compute_domain -> Domain`) y `:164` (cada regla:
`Domain(safe_eval(rule.domain_force, eval_context)) if rule.domain_force else
Domain.TRUE`). Los padres `_inherits` entran como
`Domain(parent_field_name, 'any', domain)` (`:148-150`); el resultado es
`Domain.AND(global_domains + [Domain.OR(group_domains)]).optimize(model)`.

## Estado actual

`src/addons/base/models/ir_rule.py`: `_build_domain` traduce cada regla a un
`Q` con `to_q`; `_compute_domain` combina `Q` con `&`/`|`; los padres son
`Q(fk__in=padre.filter(...))`. `_search` no puede usar un `Q` en `_to_sql`.

## Cambio

- `_build_domain` → `Domain` (la línea `:164` de la fuente).
- `_compute_domain` → `Domain`, con la forma de la fuente; se conservan la
  memoización y los parámetros explícitos `group_ids`/`user` de este árbol.
- `_parent_rule_domains` → `Domain(fk, 'any', dominio_del_padre)`.
- Los consumidores de `Q` convierten **en su sitio** con
  `Domain._to_q(model)`: `_get_failing`, `_failing_rules`,
  `RuleScopedManager.for_current_company`. No se añade un segundo método que
  devuelva `Q`: sería un mecanismo paralelo.
- Las pruebas que filtran con el `Q` (`tests/unit/base/test_ir_rule.py`,
  `test_ir_rule_access_error.py`) pasan al mismo `_to_q`.

## Riesgo medido antes de implementar

`to_q(domain)` se llamaba **sin modelo**; `Domain._to_q(model)` resuelve los
campos contra el modelo. Una regla que nombre un campo inexistente fallaba al
consultar y ahora falla al compilar: misma conducta visible. Lo que puede
cambiar es la semántica de borde (sección 4 del análisis), que ahora sigue a
la referencia. La regresión que lo mide: `tests/unit/base`, `tests/unit/company`,
`tests/unit/sale/test_sale_order_company_scoping.py`,
`tests/integration/base`, `tests/integration/company`,
`tests/integration/test_orm`.

## Pruebas (RED)

`tests/unit/base/test_ir_rule_domain.py`: `_compute_domain` devuelve `Domain`;
regla vacía → `Domain.TRUE`; globales con `AND`, de grupo con `OR`; un hijo
`_inherits` recibe la regla del padre como `any` sobre su FK; y el mismo
`Domain` filtra en Django (`_to_q`) y en SQL (`_to_sql`) las mismas filas.
