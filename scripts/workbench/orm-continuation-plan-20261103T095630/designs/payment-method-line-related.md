# Unidad `account-payment-method-line-related-0515`

Cadena: `designs/payment-method-line-chain.md` §4, unidad 1.

## Referencia

`odoo19c: addons/account/models/account_payment_method.py:122-129`:
`default_account_id = fields.Many2one(related='journal_id.default_account_id')`,
`code = fields.Char(related='payment_method_id.code')`,
`payment_type = fields.Selection(related='payment_method_id.payment_type')`,
`company_id = fields.Many2one(related='journal_id.company_id')`. Ninguno
almacenado. El dominio de `inbound_payment_method_line_ids`
(`odoo19c: addons/account/models/account_journal.py:205-209`) filtra por
`payment_type`: el campo relacionado tiene que poder ir a SQL.

## Binario y nuestro estado

Hoy `code`, `payment_type`, `company` y `default_account` son `property` de
Python (`addons/account/models/account_payment_method.py`, bloque «Odoo
related fields»): un dominio sobre ellos no se traduce. El idioma vigente
para un relacionado sin columna es la forma N de ADR-029
(`addons/account/models/account_journal.py`, `bank_id`): el nombre de la
fuente, `related=` con nuestras rutas y `store=False` explícito.

## Cambio

`code`, `payment_type`, `company_id`, `default_account_id` como campos
relacionados no almacenados, en lugar de las cuatro `property`. Consumidor
medido: `tests/unit/account/test_account_payment_methods_and_terms.py`
(`line.default_account`) pasa a `default_account_id`. Sin migración: no hay
columna.

## Pruebas

`tests/unit/account/test_payment_method_line_related.py`: valores de los
cuatro; búsqueda `[('payment_type', '=', 'inbound')]` que separa una línea
entrante de una saliente; ninguno crea columna. Anulación: con
`payment_type` de nuevo como `property`, cae la búsqueda.
