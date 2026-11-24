# Account U5 — el modelo de conciliación y su línea adoptan `BaseModel`

Fecha: 2026-11-24T08:24:24. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/account-basemodel-adoption-research.md`, unidad U5.

Referencia (`odoo-tools@abe4040ec1`, Odoo 19 Community):
odoo19c: addons/account/models/account_reconcile_model.py:8-13 —
`account.reconcile.model.line`, `_inherit = ['analytic.mixin']`,
`_order = 'sequence, id'`, `_check_company_auto = True`;
odoo19c: addons/account/models/account_reconcile_model.py:91-96 —
`account.reconcile.model`, `_inherit = ['mail.thread']`,
`_order = 'sequence, id'`, `_check_company_auto = True`.

## Qué cambia

1. Las dos clases pasan de `(models.RecordLoaderMixin, models.Model)` a
   `models.BaseModel`.
2. Las dos declaran `_check_company_auto = True`, que la fuente declara y
   este árbol no.
3. `line_ids` pasa a recordset (los dos extremos son `BaseModel`):
   `compute_mapped_partner` lo itera en vez de `.all()`, y la prueba del
   plan contable cuenta las líneas con `len` y lee la única con `[0]`.
   `match_partner_ids` apunta a `res.partner`, que aún no es `BaseModel`, y
   conserva el gestor.
4. La carga del plan contable asignaba la cuenta a las líneas de las dos
   reglas con `update()` del gestor; sobre el recordset pasa a
   `write({'account': …})`, la forma de la fuente.

Prueba: `tests/unit/account/test_account_reconcile_model_basemodel.py` y
`tests/unit/account/test_chart_template.py`.

## Citas de la fuente por archivo

- `addons/account/models/account_reconcile_model.py`: odoo19c: addons/account/models/account_reconcile_model.py:8-13
  y odoo19c: addons/account/models/account_reconcile_model.py:91-96.
- `addons/account/models/chart_template.py`: odoo19c: addons/account/models/chart_template.py:785-792.

Pruebas: `tests/unit/account/test_account_reconcile_model_basemodel.py` y
`tests/unit/account/test_chart_template.py`.

## Símbolos tocados por archivo

- `addons/account/models/account_reconcile_model.py`: `AccountReconcileModel`, `AccountReconcileModelLine`, `compute_mapped_partner`.
- `addons/account/models/chart_template.py`: `wire_bank_fees_account`.

## Lo que este corte no cierra

Los tres campos de contacto de la regla —`partner` y `mapped_partner`
(Many2one) y `match_partner_ids` (Many2many)— apuntan a
`settings.AUTH_USER_MODEL`; la fuente los declara sobre `res.partner`
(odoo19c: addons/account/models/account_reconcile_model.py:20-21 y
odoo19c: addons/account/models/account_reconcile_model.py:118-119). Es un
cambio de comodelo con migración de datos y no de herencia, así que va en
la unidad sucesora `account-reconcile-partner-comodel-0397`, la siguiente
de la cola. La prueba de U5 no depende de ese comodelo.
