# Bloque D: las filas `set null` del contrato de política de borrado

Unidad: `orm-fk-delete-policy-contract-0515` (TASK-API-0515). Referencia:
odoo-tools `abe4040ec1`. Escrito el 2026-11-17 durante la F2 de
`29285b00`, antes de tocar ningún modelo de este bloque.

## Población (reproducida por el coordinador)

`remaining_rows` sobre `outputs/fk_reference_ondelete.tsv` con
introspección de Django en `29285b00`: quedan **71** filas en `CASCADE`
(46 `set null`, 25 `restrict`); con las 22 de `CORRECTED` son las 93 del
contrato. El denominador no cambia. Las 46 `set null` declaran
`null=True`. La cifra «20 y 47» de `restrict-ondelete-non-company.md` queda
**OUTDATED**: son 25 y 46.

Este bloque toma **44** de las 46. Quedan fuera dos, cada una con su
motivo:

| Fila | Motivo | Sucesor |
|---|---|---|
| `hr.HrVersion.employee` | `hr.employee` hereda por `_inherits` de `hr.version`; falta medir qué borra la fuente al borrar un empleado | bloque E, con esa medición |
| `project.ProjectTask.project` | la fuente borra las tareas en `project.project.unlink` antes de `super()` (`odoo19c: addons/project/models/project_project.py:714`); aquí `Project` no declara `unlink` | bloque E, con ese `unlink` |

## Contrato de la referencia

Un `Many2one` no obligatorio sin `ondelete` es `set null`
(`odoo19c: odoo/orm/fields_relational.py:274-282`): borrar el destino deja
la fila con la columna vacía.

## Cambio

`on_delete=models.SET_NULL` en cada campo y un `AlterField` por aplicación.
Ningún campo cambia de nulabilidad.

### `account` — migración `0044_set_null_ondelete_block_d`

| Campo | Fuente |
|---|---|
| `account.AccountBankStatement`.`company` | `odoo19c: addons/account/models/account_bank_statement.py:58` |
| `account.AccountBankStatement`.`journal` | `odoo19c: addons/account/models/account_bank_statement.py:68` |
| `account.AccountFiscalPositionAccount`.`company` | `odoo19c: addons/account/models/partner.py:318` |
| `account.AccountJournalGroup`.`company` | `odoo19c: addons/account/models/account_journal.py:23` |
| `account.AccountLockException`.`user` | `odoo19c: addons/account/models/account_lock_exception.py:37` |
| `account.AccountMove`.`company` | `odoo19c: addons/account/models/account_move.py:175` |
| `account.AccountMoveLine`.`company_id` | `odoo19c: addons/account/models/account_move_line.py:55` |
| `account.AccountPaymentTerm`.`company` | `odoo19c: addons/account/models/account_payment_term.py:27` |
| `account.AccountReconcileModelLine`.`company` | `odoo19c: addons/account/models/account_reconcile_model.py:16` |
| `account.AccountReportColumn`.`report` | `odoo19c: addons/account/models/account_report.py:940` |
| `account.AccountTaxRepartitionLine`.`company` | `odoo19c: addons/account/models/account_tax.py:5264` |

### `base` — migración `0118_set_null_ondelete_block_d`

| Campo | Fuente |
|---|---|
| `base.IrActionsServer`.`crud_model_id` | `odoo19c: odoo/addons/base/models/ir_actions.py:652` |
| `base.IrActionsServer`.`link_field_id` | `odoo19c: odoo/addons/base/models/ir_actions.py:658` |
| `base.IrActionsServer`.`sequence_id` | `odoo19c: odoo/addons/base/models/ir_actions.py:688` |
| `base.IrActionsServer`.`update_related_model_id` | `odoo19c: odoo/addons/base/models/ir_actions.py:666` |
| `base.IrDemoFailure`.`wizard` | `odoo19c: odoo/addons/base/models/ir_demo_failure.py:12` |
| `base.IrSequence`.`company` | `odoo19c: odoo/addons/base/models/ir_sequence.py:150` |
| `base.ResCurrencyRate`.`company` | `odoo19c: odoo/addons/base/models/res_currency.py:376` |
| `base.ResDeviceLog`.`user` | `odoo19c: odoo/addons/base/models/res_device.py:28` |
| `base.ServerActionHistoryWizard`.`action` | `odoo19c: odoo/addons/base/models/ir_actions.py:477` |

### `mail` — migración `0011_set_null_ondelete_block_d`

| Campo | Fuente |
|---|---|
| `mail.MailAlias`.`alias_parent_model` | `odoo19c: addons/mail/models/mail_alias.py:64` |

### `mrp` — migración `0007_set_null_ondelete_block_d`

| Campo | Fuente |
|---|---|
| `mrp.MrpBom`.`product` | `odoo19c: addons/mrp/models/mrp_bom.py:35` |

### `product` — migración `0024_set_null_ondelete_block_d`

| Campo | Fuente |
|---|---|
| `product.ProductCombo`.`company` | `odoo19c: addons/product/models/product_combo.py:14` |
| `product.ProductComboItem`.`company` | `odoo19c: addons/product/models/product_combo_item.py:12` |
| `product.ProductPricelist`.`company` | `odoo19c: addons/product/models/product_pricelist.py:43` |
| `product.ProductSupplierinfo`.`company` | `odoo19c: addons/product/models/product_supplierinfo.py:33` |
| `product.ProductSupplierinfo`.`product` | `odoo19c: addons/product/models/product_supplierinfo.py:42` |
| `product.ProductSupplierinfo`.`purchase_requisition_line` | `odoo19c: addons/purchase_requisition/models/product.py:11` |
| `product.ProductTemplate`.`company` | `odoo19c: addons/product/models/product_template.py:124` |
| `product.ProductUom`.`company` | `odoo19c: addons/product/models/product_uom.py:16` |

### `sales_team` — migración `0011_set_null_ondelete_block_d`

| Campo | Fuente |
|---|---|
| `sales_team.CrmTeam`.`company_id` | `odoo19c: addons/sales_team/models/crm_team.py:88` |

### `stock` — migración `0031_set_null_ondelete_block_d`

| Campo | Fuente |
|---|---|
| `stock.StockLocation`.`company` | `odoo19c: addons/stock/models/stock_location.py:60` |
| `stock.StockMove`.`picking` | `odoo19c: addons/stock/models/stock_move.py:106` |
| `stock.StockMove`.`scrap` | `odoo19c: addons/stock/models/stock_move.py:139` |
| `stock.StockMoveLine`.`lot` | `odoo19c: addons/stock/models/stock_move_line.py:48` |
| `stock.StockMoveLine`.`move` | `odoo19c: addons/stock/models/stock_move_line.py:26` |
| `stock.StockMoveLine`.`picking` | `odoo19c: addons/stock/models/stock_move_line.py:21` |
| `stock.StockPackage`.`company` | `odoo19c: addons/stock/models/stock_package.py:38` |
| `stock.StockPackageType`.`company` | `odoo19c: addons/stock/models/stock_package_type.py:30` |
| `stock.StockQuant`.`company` | `odoo19c: addons/stock/models/stock_quant.py:56` |
| `stock.StockRoute`.`company` | `odoo19c: addons/stock/models/stock_location.py:533` |
| `stock.StockRule`.`company` | `odoo19c: addons/stock/models/stock_rule.py:67` |
| `stock.StockRule`.`warehouse` | `odoo19c: addons/stock/models/stock_rule.py:103` |
| `stock.StockStorageCategory`.`company` | `odoo19c: addons/stock/models/stock_storage_category.py:22` |

## Pruebas

- `tests/unit/orm/test_delete_policy_contract.py`: las filas pasan a
  `CORRECTED`; cada una corre sin `xfail` y compara el `on_delete` del campo
  con el de la fuente. El conteo de población (93, 48, 45) no se toca.
- `tests/unit/orm/test_set_null_ondelete_block_d.py`, de comportamiento,
  sobre filas cuyo destino se puede borrar sin otra guarda:

| Caso | Espera |
|---|---|
| borrar un usuario con registros de dispositivo (`ResDeviceLog.user`) | la fila sigue, `user` nulo (hoy `xfail` en el contrato; pasa a correr) |
| borrar un movimiento con líneas (`StockMoveLine.move`) | la línea sigue, `move` nulo |
| borrar un lote con líneas (`StockMoveLine.lot`) | la línea sigue, `lot` nulo |
| borrar un informe con columnas (`AccountReportColumn.report`) | la columna sigue, `report` nulo |
| borrar una secuencia usada por una acción (`IrActionsServer.sequence_id`) | la acción sigue, `sequence_id` nulo |

Anulación: devolver un campo a `CASCADE` tumba su fila del contrato y su
caso de comportamiento, y ninguna otra.

*Métrica:* `remote_field.on_delete` de cada campo y, en cinco filas, la
fila hija leída de la base tras borrar el destino.
*Ciega a:* el comportamiento de las filas hacia `res.company`, cuyo borrado
lo rehúsan otras relaciones `restrict`; para ellas sólo se mide el atributo.
