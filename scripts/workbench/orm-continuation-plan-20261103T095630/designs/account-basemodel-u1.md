# Account U1 — los cuatro catálogos hoja adoptan `BaseModel`

Fecha: 2026-11-24T02:51:20. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/account-basemodel-adoption-research.md`, unidad U1
(catálogos hoja, sin `save` ni `delete` propios y sin gestores en
producción).

Referencia (`odoo-tools@abe4040ec1`, Odoo 19 Community):
odoo19c: addons/account/models/account_incoterms.py:7-9 —
`_name = 'account.incoterms'`, `_description = 'Incoterms'`;
odoo19c: addons/account/models/account_lock_exception.py:11-13 —
`_name = 'account.lock_exception'`, `_description = "Account Lock Exception"`;
odoo19c: addons/account/models/account_cash_rounding.py:8-17 —
`_name = 'account.cash.rounding'`, `_description = 'Account Cash Rounding'`,
`_check_company_auto = True`;
odoo19c: addons/account/models/account_journal.py:16-35 —
`_name = 'account.journal.group'`, `_description = "Account Journal Group"`,
`_check_company_auto = True`,
`_check_company_domain = models.check_company_domain_parent_of`,
y `excluded_journal_ids` como `Many2many` hacia `account.journal`.
Sus filas ACL ya están en `addons/account/security/ir.model.access.csv`,
iguales a las de la fuente (odoo19c: addons/account/security/ir.model.access.csv:2-3,
odoo19c: addons/account/security/ir.model.access.csv:13-14,
odoo19c: addons/account/security/ir.model.access.csv:18-19 y
odoo19c: addons/account/security/ir.model.access.csv:57-59).

## Qué cambia

1. Las cuatro clases pasan de `(models.RecordLoaderMixin, models.Model)` a
   `models.BaseModel`, que ya incluye las dos.
2. `AccountCashRounding` declara `_check_company_auto = True` y
   `AccountJournalGroup` declara `_check_company_auto = True` y
   `_check_company_domain = models.check_company_domain_parent_of`, como la
   fuente; hoy no los declaraban.
3. `excluded_journals` del grupo pasa a recordset (los dos extremos son
   `BaseModel`). Nadie fuera del propio modelo lo lee.

`Meta.ordering` se conserva en las cuatro: la fuente no declara `_order`
(ordena por `id`) y estas clases ordenaban ya por otra columna; cambiarlo
mueve el orden de lectura de quienes las listan sin que ninguna obligación
de esta unidad lo pida. Sucesor: `account-leaf-ordering-0397`.

Prueba: `tests/unit/account/test_account_leaf_catalogs_basemodel.py`.

## Citas de la fuente por archivo

- `addons/account/models/account_incoterms.py`: odoo19c: addons/account/models/account_incoterms.py:7-22.
- `addons/account/models/account_lock_exception.py`: odoo19c: addons/account/models/account_lock_exception.py:11-13.
- `addons/account/models/account_cash_rounding.py`: odoo19c: addons/account/models/account_cash_rounding.py:8-17.
- `addons/account/models/account_journal_group.py`: odoo19c: addons/account/models/account_journal.py:16-35.

Pruebas: `tests/unit/account/test_account_leaf_catalogs_basemodel.py`.

## Símbolos tocados por archivo

- `addons/account/models/account_incoterms.py`: `AccountIncoterms`.
- `addons/account/models/account_lock_exception.py`: `AccountLockException`.
- `addons/account/models/account_cash_rounding.py`: `AccountCashRounding`.
- `addons/account/models/account_journal_group.py`: `AccountJournalGroup`.

## Lo que este corte no cierra

`Meta.ordering` frente al `id` de la fuente en las cuatro: sucesor
`account-leaf-ordering-0397`.
