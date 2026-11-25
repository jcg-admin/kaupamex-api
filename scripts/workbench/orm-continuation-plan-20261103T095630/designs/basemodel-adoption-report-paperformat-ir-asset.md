# Adopción de BaseModel: report.paperformat + ir.asset (basemodel-adoption-0397)

## Referencia

- `odoo19c: odoo/addons/base/models/report_paperformat.py:165` — `class ReportPaperformat(models.Model)`, `_name = 'report.paperformat'`.
- `odoo19c: odoo/addons/base/models/ir_asset.py:51` — `class IrAsset(models.Model)`, `_name = 'ir.asset'`.
- ACL (`ir.model.access.csv:99,121-122`): `access_ir_asset_group_system`,
  `paperformat_access_portal` y `paperformat_access_employee`, ya sembradas en
  `src/addons/base/security/ir_model_access.py`. La fuente no declara record
  rules para ninguno de los dos (`base_security.xml`).

## Cambio

- `ReportPaperformat(models.BaseModel)` e `IrAsset(models.BaseModel)`, en lugar
  de `RecordLoaderMixin, models.Model` (BaseModel ya lleva el mixin de carga).
  Sin migración (`./kaupamex-bin makemigrations base --check --dry-run` → sin
  cambios).
- Los consumidores de producción (`res_company.py`, `report_paperformat_data.py`,
  `website/models/website.py`) leen y siembran por el gestor de Django, que no
  pasa por la ACL: no cambian.

## Pruebas

- `tests/unit/base/test_paperformat_asset_basemodel.py` (nuevo).
- Subconjunto derivado (`ReportPaperformat|IrAsset|paperformat|ir.asset|ir_asset|IrActionsReport|html_editor`
  en `tests/`, 23 archivos): 466 passed, 26 skipped.

## Anulación

Revertir sólo `IrAsset` a `RecordLoaderMixin, models.Model`: cae exactamente
`test_paperformat_and_asset_are_basemodel[IrAsset]` (1 de 2). Restaurado y
verificado con `cmp`.
