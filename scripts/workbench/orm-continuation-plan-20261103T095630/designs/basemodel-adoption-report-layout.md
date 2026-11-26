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

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `ReportLayout` sobre `models.BaseModel` con `_name`, `_description`, `_order` | `src/addons/base/models/report_layout.py` | `odoo19c: odoo/addons/base/models/report_layout.py:7-10` |
| campo `view` de `ReportLayout` obligatorio | ídem | `odoo19c: odoo/addons/base/models/report_layout.py:12` |
| fila `access_report_layout` de `_ACCESS` | `src/addons/base/security/ir_model_access.py` | `odoo19c: odoo/addons/base/security/ir.model.access.csv:123` |
| migración `0139_report_layout_view_required` | `src/addons/base/migrations/0139_report_layout_view_required.py` | ídem |

Prueba: `tests/unit/base/test_report_layout_basemodel.py`.

Una fila sin vista hace fallar el `ALTER` de `0139` a propósito: no se le
inventa una vista ni se borra. La base de pruebas tenía 0 filas.

Anulaciones, restauradas con `cmp` y con la restricción devuelta
(`is_nullable = NO`, medido):

- sin el cambio de base: caen exactamente los dos casos de ACL (interno
  crea y lee; portal no lee) y pasa el de la vista;
- con `view_id` nullable en la base (`ALTER ... DROP NOT NULL` sobre la base
  de pruebas): cae exactamente `test_a_layout_needs_a_view`.
