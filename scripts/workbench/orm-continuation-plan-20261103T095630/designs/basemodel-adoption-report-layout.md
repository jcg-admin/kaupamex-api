# report.layout sobre BaseModel

Unidad de `basemodel-adoption-0397` (TASK-API-0397). Mapa de consumidores
preparado por un subagente de sólo lectura y verificado contra la fuente.

## Fuente medida

`odoo19c: odoo/addons/base/models/report_layout.py:7-17`: `_name`,
`_description = 'Report Layout'`, `_order = 'sequence, id'`; `view_id`
Many2one **obligatorio** a `ir.ui.view`, `image`, `pdf`, `sequence`
(default 50), `name`. Sin métodos.

ACL `access_report_layout`, `group_user`, 1,1,1,1
(`odoo19c: odoo/addons/base/security/ir.model.access.csv:123`). Sin reglas.

## Puerto antes de la unidad

`src/addons/base/models/report_layout.py`: los cinco campos, `view` nullable
con la razón *«hasta que ir.ui.view esté portado»*. **La prosa heredada ya
no se sostiene**: `IrUiView` existe (`src/addons/base/models/ir_ui_view.py`).
Sin atributos de clase; sin fila de ACL. Ningún consumidor escribe filas.

## Cambio

1. `ReportLayout(models.BaseModel, TimeStampedModel)` con los tres atributos
   de clase.
2. `view` obligatorio, como el `required=True` de la fuente, con migración;
   el docstring deja la razón caducada.
3. Fila de ACL `access_report_layout` para `group_user` y su siembra.

## Controles previstos

- un usuario interno crea y lee diseños (ACL de `group_user`);
- un usuario sin `group_user` (portal) no los lee;
- crear un diseño sin vista falla.

Prueba: `tests/unit/base/test_report_layout_basemodel.py`.
