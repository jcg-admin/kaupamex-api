# Bloque F: las filas `restrict` del contrato que sólo cambian de política

Unidad: `orm-fk-delete-policy-contract-0515` (TASK-API-0515). Referencia:
odoo-tools `abe4040ec1`. Escrito el 2026-11-18 durante la F2 de `a58ac65d`,
antes de tocar ningún modelo de este bloque.

## Población

De las 25 filas `restrict` que siguen en `CASCADE` (reproducidas en
`designs/set-null-ondelete-block-d.md`), este bloque toma **23**: 22 hacia
`res.company` y `stock.StockRule.picking_type`. Quedan fuera las dos de
`account.AccountPartialReconcile` (bloque C): la fuente quita la
conciliación en `account.move.line.unlink` antes de borrar, y ese `unlink`
no está portado.

## Contrato de la referencia

Un `Many2one` obligatorio sin `ondelete` es `restrict`
(`odoo19c: odoo/orm/fields_relational.py:274-282`): la base rehúsa borrar
el destino mientras existan filas que lo citen. `res.company.unlink` no
borra antes a ningún hijo: es `super().unlink()` más vaciar la caché
(`odoo19c: odoo/addons/base/models/res_company.py:347-353`).
`stock.picking.type` no redefine `unlink` (el de
`odoo19c: addons/stock/models/stock_picking.py:1170` es de `stock.picking`).

`account.AccountBankStatementLine.company` es `related` y obligatorio en la
fuente; el investigador concluye que su FK física es `set null` sobre
columna `NOT NULL`, que también rehúsa el borrado. No se observó el DDL
(UNVERIFIED); `PROTECT` da la misma conducta y es lo que la matriz pide.

## Cambio

`on_delete=models.PROTECT` en cada campo y un `AlterField` por aplicación,
con el nombre `restrict_ondelete_block_f`. Ninguna nulabilidad cambia: cinco
campos son `null=True` aquí y obligatorios en la fuente
(`AccountBankStatementLine.company`, `PurchaseOrder.company_id`,
`SaleOrder.company`, `StockPickingType.company`, `StockRule.picking_type`);
esa divergencia es anterior y queda como sucesor.

### `account` — migración `0045_restrict_ondelete_block_f`

| Campo | Fuente |
|---|---|
| `account.AccountBankStatementLine`.`company` | `odoo19c: addons/account/models/account_bank_statement_line.py:38` |
| `account.AccountFiscalPosition`.`company` | `odoo19c: addons/account/models/partner.py:37` |
| `account.AccountGroup`.`company` | `odoo19c: addons/account/models/account_account.py:1508` |
| `account.AccountJournal`.`company` | `odoo19c: addons/account/models/account_journal.py:172` |
| `account.AccountLockException`.`company` | `odoo19c: addons/account/models/account_lock_exception.py:29` |
| `account.AccountPayment`.`company` | `odoo19c: addons/account/models/account_payment.py:30` |
| `account.AccountReconcileModel`.`company` | `odoo19c: addons/account/models/account_reconcile_model.py:102` |
| `account.AccountReportExternalValue`.`company` | `odoo19c: addons/account/models/account_report.py:963` |
| `account.AccountTax`.`company` | `odoo19c: addons/account/models/account_tax.py:126` |
| `account.AccountTaxGroup`.`company` | `odoo19c: addons/account/models/account_tax.py:34` |

### `account_edi_proxy_client` — migración `0007_restrict_ondelete_block_f`

| Campo | Fuente |
|---|---|
| `account_edi_proxy_client.AccountEdiProxyUser`.`company_id` | `odoo19c: addons/account_edi_proxy_client/models/account_edi_proxy_user.py:37` |

### `analytic` — migración `0012_restrict_ondelete_block_f`

| Campo | Fuente |
|---|---|
| `analytic.AccountAnalyticLine`.`company` | `odoo19c: addons/analytic/models/analytic_line.py:204` |

### `purchase` — migración `0026_restrict_ondelete_block_f`

| Campo | Fuente |
|---|---|
| `purchase.PurchaseOrder`.`company_id` | `odoo19c: addons/purchase/models/purchase_order.py:160` |

### `purchase_requisition` — migración `0005_restrict_ondelete_block_f`

| Campo | Fuente |
|---|---|
| `purchase_requisition.PurchaseRequisition`.`company` | `odoo19c: addons/purchase_requisition/models/purchase_requisition.py:30` |

### `sale` — migración `0019_restrict_ondelete_block_f`

| Campo | Fuente |
|---|---|
| `sale.SaleOrder`.`company` | `odoo19c: addons/sale/models/sale_order.py:60` |

### `stock` — migración `0032_restrict_ondelete_block_f`

| Campo | Fuente |
|---|---|
| `stock.StockMoveLine`.`company` | `odoo19c: addons/stock/models/stock_move_line.py:29` |
| `stock.StockPackageHistory`.`company` | `odoo19c: addons/stock/models/stock_package_history.py:11` |
| `stock.StockPickingType`.`company` | `odoo19c: addons/stock/models/stock_picking.py:130` |
| `stock.StockPutawayRule`.`company` | `odoo19c: addons/stock/models/product_strategy.py:60` |
| `stock.StockRule`.`picking_type` | `odoo19c: addons/stock/models/stock_rule.py:87` |
| `stock.StockWarehouse`.`company` | `odoo19c: addons/stock/models/stock_warehouse.py:37` |
| `stock.StockWarehouseOrderpoint`.`company` | `odoo19c: addons/stock/models/stock_orderpoint.py:68` |

### `website` — migración `0014_restrict_ondelete_block_f`

| Campo | Fuente |
|---|---|
| `website.Website`.`company` | `odoo19c: addons/website/models/website.py:124` |

## Consumidores medidos

Borrados de una empresa en el árbol (`grep` sobre `tests addons src`): cinco
sitios, todos en pruebas
(`tests/integration/base_setup/test_company_delete_with_a_tableless_form.py:56`,
`tests/integration/base/test_migration_seeds_survive_flush.py:210`,
`tests/unit/base/test_ir_model_data_loader.py:249`,
`tests/unit/base/test_ir_attachment.py:159`,
`tests/unit/base/test_ir_model_data_xmlid.py:98`); ninguno en código de
producto. Si alguno crea hijos de estas filas, la F2 lo dirá.

## Pruebas

- `tests/unit/orm/test_delete_policy_contract.py`: las 23 filas pasan a
  `CORRECTED`; `test_deleting_a_picking_type_with_rules_is_refused` deja de
  ser `xfail` y su gemela «hoy» se retira.
- `tests/unit/orm/test_restrict_ondelete_block_f.py`: borrar una empresa
  con un diario, con un almacén, con un impuesto o con un sitio web se
  rehúsa (`ProtectedError`) y el hijo sigue; una empresa sin hijos se borra
  (control).

Anulación: devolver un campo a `CASCADE` tumba su fila del contrato y su
caso de comportamiento, y ninguna otra.

*Métrica:* `remote_field.on_delete` de cada campo y, en cuatro filas, que
el borrado se rehúsa.
*Ciega a:* el mensaje con que la fuente rehúsa (un error de integridad de
la base, no un `UserError`), que aquí es `ProtectedError`.
