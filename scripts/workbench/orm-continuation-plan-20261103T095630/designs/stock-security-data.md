# U0-0 de `stock` — grupos, privilegio, reglas y ACL por manifiesto

Fecha: 2026-11-22T23:31:05. Primera unidad de la partición de
`outputs/stock-basemodel-adoption-research.md`. Sigue el procedimiento de
`security-data-by-manifest.md` (`sales_team`, `uom`, `hr`).

## Contrato de la referencia

`odoo19c: addons/stock/__manifest__.py:20-21` declara en `data`
`security/stock_security.xml` y `security/ir.model.access.csv`. El XML crea
el privilegio `res_groups_privilege_inventory`, los grupos
`group_stock_user` y `group_stock_manager` (con su implicación) y once
grupos ocultos, y trece reglas multiempresa en `noupdate="1"`
(`odoo19c: addons/stock/security/stock_security.xml:1-169`). El CSV tiene
77 filas.

## Estado medido

- `addons/stock/security/` no existía y el manifiesto no declaraba `data`.
- `base` no siembra grupos de `stock`: su `res_groups_data.py` lo declara
  bloqueado hasta que `stock` siembre los suyos.
- `base.module_category_supply_chain` lo genera
  `src/addons/base/migrations/0090_module_category_tree.py` desde el
  `category` del manifiesto (`Supply Chain/Inventory`).
- Medido estáticamente contra los `_name` declarados: de las 52 referencias
  a modelo del CSV y el XML, 25 tienen `_name` aquí y 27 no.

## Decisión

Copia fiel (LGPL-3) de los dos archivos, en `data`, con cuatro omisiones
declaradas en la cabecera del XML:

| Omisión | Razón | Sucesor |
|---|---|---|
| 33 filas del CSV | sus modelos no se portan aquí: asistentes y transitorios (`stock.backorder.confirmation`, `stock.return.picking`…), informes (`report.stock.quantity`, `stock.traceability.report`…), `barcodes.*` y `update.product.attribute.value` | — |
| 5 de esas filas y dos reglas sobre `stock.location` y `stock.route` | no declaran `_name`, así que no tienen `ir.model` | `stock-location-route-name-0397` |
| regla `report_stock_quantity_flow_comp_rule` | informe no portado | — |
| `base.user_admin` en `group_stock_manager.user_ids` | no existe en este árbol (DEC-3) | — |

## Prueba

`tests/unit/stock/test_stock_security_data.py`:

| Comprobación | Referencia |
|---|---|
| los grupos existen con su `xml_id` y `group_stock_manager` implica a `group_stock_user` | `odoo19c: addons/stock/security/stock_security.xml:10-21` |
| `stock.picking` recibe las filas de la fuente | `odoo19c: addons/stock/security/ir.model.access.csv` |
| las reglas multiempresa existen con su dominio | `odoo19c: addons/stock/security/stock_security.xml:72-163` |

Anulación: retirar los dos archivos de `data` hace caer las tres.

*Métrica:* filas de `res.groups`, `ir.model.access` e `ir.rule` que crea
una instalación nueva de `stock`.
*Ciega a:* el efecto de la ACL sobre modelos que todavía no son `BaseModel`
(lo mide cada sub-unidad al adoptarlo) y el de las reglas sobre los gestores
de Django de `stock`, que mide la suite completa.

## Bloqueo medido al ejecutar (2026-11-23)

La carga revienta en `stock_security.xml:88`, la primera regla que nombra su
modelo con `search="[('model','=','stock.picking')]"`, con
`Dominio inválido: not enough values to unpack (expected 2, got 1)`. La causa
no está en `stock`:

- `ir.model.model` guarda aquí la etiqueta de Django (`stock.StockPicking`,
  medido sobre la fila de `stock.model_stock_picking`), y ninguna fila tiene
  `model='stock.picking'`, `'stock.warehouse'` ni `'sale.order'`.
- La fuente guarda el `_name`: `'model': model._name` en
  `_reflect_model_params` (`odoo19c: odoo/addons/base/models/ir_model.py:428`).
  Nuestro `_reflect_model_params` porta las otras siete claves y fija `model`
  aparte.
- Con la búsqueda vacía, `model_id` queda nulo, `model_name` vacío, y
  `IrRule._check_domain` hace `''.split('.', 1)`.

No se esquiva reescribiendo el XML a `ref=`: sería cambiar la fuente para
tapar una divergencia de `ir.model`. Prerrequisito declarado:
`ir-model-model-is-odoo-name-0397`. Esta unidad queda en la rama
`wt/stock-security` y se retoma sobre ella.

