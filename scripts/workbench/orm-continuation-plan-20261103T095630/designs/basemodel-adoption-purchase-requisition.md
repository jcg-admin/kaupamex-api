# `purchase_requisition` sobre `BaseModel`, con su seguridad

Unidad hija `basemodel-adoption-purchase-requisition-0397` del paraguas
`basemodel-adoption-0397` (TASK-API-0397), con la forma de
`basemodel-adoption-base-automation.md` y la carga de seguridad de
`purchase-security.md`.

## Contrato medido en la referencia

- `purchase.requisition`
  (`odoo19c: addons/purchase_requisition/models/purchase_requisition.py:9`):
  `_name`, `_description`, `_inherit = ['mail.thread',
  'mail.activity.mixin']`, `_order = "id desc"`.
- `purchase.requisition.line` (mismo archivo, `:165-168`):
  `_inherit = ['analytic.mixin']`, `_rec_name = 'product_id'`.
- `purchase.order.group` (`odoo19c: addons/purchase_requisition/models/purchase.py`).
- `odoo19c: addons/purchase_requisition/security/ir.model.access.csv`: 7
  filas (dos de los transitorios ya adoptados).
- `odoo19c: addons/purchase_requisition/security/purchase_requisition_security.xml`:
  las reglas multiempresa de acuerdo y línea, y el grupo
  `group_purchase_alternatives`.
- `action_cancel` (`:118-127`) publica en cada orden cancelada
  *«Cancelled by the agreement associated to this quotation.»*;
  `action_done` (`:146-156`) rehúsa con órdenes en `draft`, `sent` o
  `to approve`.

## La prosa heredada, validada

| Afirmación de la cabecera del módulo | Medido | Veredicto |
|---|---|---|
| D-1: `mail.thread` no se hereda porque `mail` no está en `depends` | `purchase` depende de `mail`, y `MailThread`/`MailActivityMixin` son abstractos sin columnas | ya no se sostiene: se hereda, y `action_cancel` publica la nota |
| `action_done` rehúsa con órdenes vivas | el puerto mira `draft` y `sent`; la fuente también `to approve`, que `purchase.order` declara (`STATE_TO_APPROVE`) | se corrige |
| D-3: `create`/`write`/`unlink` sobre `save`/`delete` | `BaseModel` los tiene | sigue, con sucesor (abajo) |

## Cambios

1. `PurchaseRequisition` deriva de `(models.BaseModel, MailThread,
   MailActivityMixin, TimeStampedModel)`; `PurchaseRequisitionLine` de
   `(models.BaseModel, AnalyticMixin, TimeStampedModel)`;
   `PurchaseOrderGroup` de `(models.BaseModel, TimeStampedModel)`.
2. `addons/purchase_requisition/security/`: el CSV y el XML, copia fiel, en
   `data` del manifiesto en el orden de la fuente (XML primero).
3. Consumidores del API de gestor sobre accesores que pasan a recordset
   (`purchase_ids`, `line_ids`, `order_ids`): `_compute_orders_number`,
   `product`, `delete`, `action_cancel`, `action_confirm`, `action_done` y
   `PurchaseOrderGroup.implode_if_alone` (`purchase.py`, que cuenta `order_ids` con `len`; ≙ `odoo19c: addons/purchase_requisition/models/purchase.py:16-20`). `supplier_info_ids` apunta a
   `product.supplierinfo`, que no es `BaseModel`: sigue siendo un conjunto
   de consulta.
4. `action_cancel` publica la nota de la fuente con `message_post`;
   `action_done` añade `to approve`.
5. `test_basemodel_reach.py`: `purchase_requisition` sale de `PENDING`.

## Ejecución (medido al implementar)

6. D-5 se cierra en esta unidad, porque la regla
   `purchase_requisition_line_comp_rule` la necesita: cargar el XML falló con
   *«Campo inválido purchase_requisition.PurchaseRequisitionLine.company_id»*
   mientras la empresa de la línea era una `property`. La línea declara ahora
   `company_id = fields.Many2one(related='requisition.company', store=True,
   db_column='company_id')`, en la forma C de ADR-029 que exige
   `scripts/check_fk_naming.py` a toda FK nueva (F2 de `76917813`)
   (≙ `odoo19c: addons/purchase_requisition/models/purchase_requisition.py:181`),
   con la migración `0006_purchaserequisitionline_company`, que rellena las
   filas existentes con la empresa de su acuerdo.
7. Del CSV salen dos filas, las de `purchase.requisition.alternative.warning`
   y `purchase.requisition.create.alternative`: son transitorios abstractos,
   sin tabla ni fila en `ir.model`, así que `model_*` no resuelve. Es el caso
   que `account-security.md` declaró para once asistentes de `account`. Se
   declaran en el manifiesto; sucesor `transient-wizard-tables-0397`.
8. Las acciones que esta unidad toca (`action_confirm`, `action_done`,
   `_unlink_if_draft_or_cancel`) levantan `UserError` con el texto de la
   fuente, no el `ValidationError` de Django; `_compute_ordered_qty` lee
   `line_ids` como recordset.

## Fuera de esta unidad, con su sucesor

- D-3: el cuerpo de `save`/`delete` pasa a `create`/`write`/`unlink` con la
  forma de la fuente — `purchase-requisition-crud-0397`.
- D-2 (`tracking=True`) y D-4 (`compute` sin `store` como `property`) —
  `purchase-requisition-divergences-0397`.
- Las dos filas de los asistentes — `transient-wizard-tables-0397`.

## Pruebas

`tests/unit/purchase_requisition/test_purchase_requisition_basemodel.py`: los
tres modelos son `BaseModel` con su `_description`; el acuerdo es
`MailThread`; las 5 filas del CSV que resuelven y los tres registros del
XML; un usuario
interno sin compras no lee un acuerdo; `order_count`; `action_done` rehúsa
con `to approve`; `action_cancel` deja la nota en la orden.
