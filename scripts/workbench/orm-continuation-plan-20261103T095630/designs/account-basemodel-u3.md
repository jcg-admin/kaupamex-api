# Account U3 — `account.payment.term` y su línea adoptan `BaseModel`

Fecha: 2026-11-24T04:04:55. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/account-basemodel-adoption-research.md`, unidad U3.

Referencia (`odoo-tools@abe4040ec1`, Odoo 19 Community):
odoo19c: addons/account/models/account_payment_term.py:11-15 —
`_name = 'account.payment.term'`, `_description = "Payment Terms"`,
`_order = "sequence, id"`,
`_check_company_domain = models.check_company_domain_parent_of`;
odoo19c: addons/account/models/account_payment_term.py:281-284 —
`_name = 'account.payment.term.line'`, `_description = "Payment Terms Line"`,
`_order = "id"`. `_check_lines` lee `terms.line_ids` y
`len(terms.line_ids)` (odoo19c: addons/account/models/account_payment_term.py:157-169);
`_compute_days` y `_compute_value_amount` recorren las hermanas por
`line.payment_id.line_ids` (odoo19c: addons/account/models/account_payment_term.py:350-367).

## Qué cambia

1. Las dos clases pasan de `(models.RecordLoaderMixin, models.Model)` a
   `models.BaseModel`.
2. `AccountPaymentTerm` declara `_check_company_domain`
   (`classmethod(models.check_company_domain_parent_of)`, la forma de este
   árbol).
3. `line_ids` pasa a recordset: `_check_lines` y `_compute_terms` lo
   iteran y cuentan con `len`, como la fuente; `_compute_days` y
   `_compute_value_amount` filtran las hermanas del recordset.
4. `payment_term_id` de `sale.order` y `purchase.order` pasa a recordset
   (los dos extremos son `BaseModel`).

Prueba: `tests/unit/account/test_account_payment_term_basemodel.py`.

## Citas de la fuente por archivo

- `addons/account/models/account_payment_term.py`: odoo19c: addons/account/models/account_payment_term.py:11-15,
  odoo19c: addons/account/models/account_payment_term.py:157-200,
  odoo19c: addons/account/models/account_payment_term.py:281-284
  y odoo19c: addons/account/models/account_payment_term.py:350-367.

Pruebas: `tests/unit/account/test_account_payment_term_basemodel.py`.

## Símbolos tocados por archivo

Se completa al implementar.

## Lo que este corte no cierra

Se completa al implementar.
