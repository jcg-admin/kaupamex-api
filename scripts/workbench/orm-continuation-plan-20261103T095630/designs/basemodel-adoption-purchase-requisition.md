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
   `PurchaseOrderGroup` (`purchase.py`). `supplier_info_ids` apunta a
   `product.supplierinfo`, que no es `BaseModel`: sigue siendo un conjunto
   de consulta.
4. `action_cancel` publica la nota de la fuente con `message_post`;
   `action_done` añade `to approve`.
5. `test_basemodel_reach.py`: `purchase_requisition` sale de `PENDING`.

## Fuera de esta unidad, con su sucesor

- D-3: el cuerpo de `save`/`delete` pasa a `create`/`write`/`unlink` con la
  forma de la fuente — `purchase-requisition-crud-0397`.
- D-2 (`tracking=True`), D-4 (`compute` sin `store` como `property`) y D-5
  (`company_id` de la línea) — `purchase-requisition-divergences-0397`.

## Pruebas

`tests/unit/purchase_requisition/test_purchase_requisition_basemodel.py`: los
tres modelos son `BaseModel` con su `_description`; el acuerdo es
`MailThread`; las 7 filas del CSV y los tres registros del XML; un usuario
interno sin compras no lee un acuerdo; `order_count`; `action_done` rehúsa
con `to approve`; `action_cancel` deja la nota en la orden.
