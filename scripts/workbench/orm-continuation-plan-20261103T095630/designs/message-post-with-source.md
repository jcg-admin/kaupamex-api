# `message_post_with_source` sin QWeb (TASK-API-0121)

Fecha: 2026-11-17. Contrato: `odoo19c: addons/mail/models/mail_thread.py:2621-2711`
(`message_post_with_source`), `:3097-3150` (`_get_source_from_ref`),
`:3197-3214` (`_raise_for_invalid_parameters`).

## Autoridad, en el orden de precedencia

1. Contrato ejecutable: arriba.
2. Decisiones aprobadas: **DEC-EM-01** (React reemplaza el templating QWeb) y
   **DEC-AF-08** (se porta la responsabilidad; se sustituye el sustrato de
   presentación). QWeb no se porta.
3. Precedentes implementados: `addons/crm/models/crm_lead.py:2081-2092`
   (cuerpo compuesto en Python con el mismo contenido, `message_post`),
   `addons/base_install_request/wizard/base_module_install_request.py:101-107`.
4. TASK: **TASK-API-0121** (store, fila 202, `in_progress`); unidad
   `mail-message-post-with-source-0121`. La «#279» de stock D-1 es una cita
   en colisión (`outputs/research-message-post-and-recordset-primitives-20261117.md` §C).

## Adaptación

| Pieza de la fuente | Aquí |
|---|---|
| fuente `ir.ui.view` renderizada con `ir.qweb` | **constructor de cuerpo en Python registrado por el xmlid de la vista** (`register_source_body('purchase.track_po_line_qty_received_template')`), que recibe `(record, render_values)` y devuelve el mismo marcado que la plantilla |
| `_get_source_from_ref(str)` vía `ir.model.data` | igual primero; si el xmlid no tiene fila pero sí constructor registrado, la fuente es ese constructor. Sin fila ni constructor: el mismo `ValueError` de la fuente |
| fuente registro `ir.ui.view` | se usa el constructor de su xmlid; sin constructor, `ValueError` que nombra la decisión (no hay motor que la dibuje) |
| fuente `mail.template` | rama de plantilla: `MailTemplate.render` + `message_post` por registro con `message_type` y subtipo. El compositor (`mail.compose.message`, `_action_send_mail`) no existe: destinatarios, adjuntos y envío de correo de la rama de plantilla quedan como obligación abierta de TASK-API-0121, declarada en el docstring |
| `subtype_xmlid` → `_xmlid_to_res_id`; por defecto `mail.mt_note` | igual (`ir.model.data` local; `mail.mt_note` sembrado por `mail/migrations/0002`) |
| `_raise_for_invalid_parameters` | porte literal |
| `message_post(body=…, message_type, subtype_id, **kwargs)` | `message_post(body=…, message_type=…, subtype=<registro>)`; la firma local de `message_post` (`subtype=` en vez de `subtype_id`) es su propia divergencia, no se cambia aquí |

Consumidor que lo estrena: `PurchaseOrderLine._track_qty_received`
(`odoo19c: purchase_order_line.py:714-728`), con el cuerpo de
`purchase/data/mail_templates.xml:18-26`: «The received quantity has been
updated.», el nombre del producto, y `Received Quantity: <antes> -> <después>`.

## Controles

- xmlid de vista con constructor: cuerpo idéntico al de la plantilla, un
  mensaje por registro, subtipo `mail.mt_note` por defecto y `subtype_xmlid`
  respetado.
- xmlid inexistente sin constructor: `ValueError`; registro de otro modelo:
  `ValueError`; tipo inválido: `ValueError`.
- kwargs prohibidos (`body`, `model`, `res_id`, …): `ValueError`.
- `_track_qty_received`: publica sólo si la cantidad cambia y la orden está en
  `purchase`; nada con `accrual_entry_date`.
- Anulación: retirar el constructor registrado hace caer exactamente los
  casos de cuerpo.
