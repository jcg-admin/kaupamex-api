# RED, GREEN y controles — `ir.rule` devuelve `Domain`

Diseño: `designs/ir-rule-domain.md` (paso 1 de `designs/search-contract-analysis.md`).
Referencia: odoo-tools `abe4040ec`, `odoo/addons/base/models/ir_rule.py:141-173`.

Comando: `uv run --frozen pytest tests/unit/base/test_ir_rule_domain.py tests/unit/base/test_ir_rule.py tests/unit/base/test_ir_rule_access_error.py -q --reuse-db -p no:cacheprovider`

- RED: 4 failed en `test_ir_rule_domain.py` (devolvía `Q`).
- GREEN: 4 passed; los consumidores de `Q` en las pruebas existentes
  (`test_ir_rule.py`, `test_ir_rule_access_error.py`) fallaban con
  `ValueError: not enough values to unpack` —Django desempaquetando un
  `Domain` como si fuera un `Q`— y pasan a `Domain._to_q(ResCompany)`, la
  misma conversión que hacen los consumidores del código: 68 passed.
- Controles de anulación:
  - sin el `OR` de las reglas de grupo → caen los 4 casos que combinan grupos;
  - toda regla `TRUE` → caen los 8 que dependen de evaluar `domain_force`
    (incluido el que comprueba que el evaluador rechaza código).
- Admisión de estilo: PASS.

## Cambio colateral, y por qué

`_get_failing` materializaba los ids permitidos como lista literal
(`exclude(pk__in=list(allowed))`); ahora excluye por subconsulta
(`values('pk')`). Mismo conjunto, una consulta menos y sin literales que crecen
con la tabla (sección 4 del análisis).

## Matriz de impacto

| Eje | Contenido |
|---|---|
| Changed symbols | `IrRule._build_domain`, `_compute_domain`, `_parent_rule_domains`, `_get_failing`, `_failing_rules`, `RuleScopedManager.for_current_company`. |
| Changed behavior | El tipo de retorno pasa de `Q` a `Domain`; la semántica de borde sigue a la referencia (`optimize`). |
| Direct consumers | Los cinco métodos de arriba y las pruebas de `ir_rule`. |
| Indirect consumers | Toda comprobación de acceso por fila: `_check_access`, `_filtered_access`, los managers `scoped`. |
| Required contract tests | `test_ir_rule_domain.py`. |
| Required regression tests | `tests/unit/{orm,base,company,sale,stock,account,tools,html_editor,base_iban}`, `tests/integration/{test_orm,base,company,crm,portal}` (grep de `IrRule|ir.rule|for_current_company|_check_access|_filtered_access|scoped.`). |
| Required integration gates | Suite completa y multidb en el corte de publicación: mecanismo transversal de seguridad. |
| Previously valid evidence | Ninguna. |
| Uncovered risks | Una regla sembrada cuyo `domain_force` dependía de la conversión sin modelo de `to_q`; la regresión de arriba la mediría. |
