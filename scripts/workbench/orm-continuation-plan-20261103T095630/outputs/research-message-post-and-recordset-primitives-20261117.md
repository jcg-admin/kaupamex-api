# Investigación de sólo lectura: `message_post_with_source` y primitivas de recordset en `Uom`

Fecha: 2026-11-17. Revisión del árbol: `172361c8`. Referencia: `odoo19c@abe4040ec1`.
Dos subagentes `Explore` (sonnet), sólo lectura, sin PostgreSQL, en paralelo con
F1. Titular del harness: 81 275 y 74 797 tokens (cifra del harness, que excluye
`cache_read`; no es el costo ponderado). Verificadas aquí por el orquestador:
`ir_template_expressions.py:958` (`render` sin implementar),
`purchase/data/mail_templates.xml:18`, `mail_thread.py:2621` y la ausencia de
`addons/purchase/data/`.

## A. `message_post_with_source` (TASK-API-0121, unidad mail-message-post-with-source-0121)

Contrato (`odoo19c`):
- `MailThread.message_post_with_source`, `mail/models/mail_thread.py:2621-2711`:
  `_get_source_from_ref` → rama vista (`mail.render.mixin._render_template_qweb_view`
  y `message_post(body=…)` por registro) o rama plantilla (`mail.compose.message`
  + `_action_send_mail`); `subtype_xmlid` → `_xmlid_to_res_id`, por defecto
  `mail.mt_note`; kwargs prohibidos por `_raise_for_invalid_parameters`.
- `_get_source_from_ref`, `mail_thread.py:3097-3150`: `mail.template` o
  `ir.ui.view` por registro o xmlid; todo lo demás, `ValueError`.
- `_render_template_qweb_view`, `mail/models/mail_render_mixin.py:489-534`:
  `{}` sin ids; `_render_eval_context` (`:312-333`); `ir.qweb._render` por
  registro; error → `UserError`.

Consumidor que nos bloquea: `PurchaseOrderLine._track_qty_received`
(`purchase_order_line.py:714-728`) con la vista
`purchase.track_po_line_qty_received_template` (`purchase/data/mail_templates.xml:18-26`).
Otros consumidores: `purchase_order_line.py:316`, `purchase_order.py:1077`,
`purchase_stock/models/purchase_order.py:397`, `stock_picking_return.py:169,193`,
`stock_move_line.py:784`, `stock_picking.py:1287`, `mail_activity.py:551`,
`mail_activity_mixin.py:318`, `ir_actions_server.py:345`, `mail_thread.py:739`.

Estado local:
| Pieza | Estado |
|---|---|
| `message_post` | presente, `addons/mail/models/mail_thread.py:88`, firma propia (`subtype=`, sin `subtype_id`/`subtype_xmlid`) |
| `message_post_with_source`, `_get_source_from_ref` | ausentes |
| `mail.render.mixin`, `_render_eval_context`, `_render_template_qweb_view` | ausentes |
| `ir.qweb._render` | **ausente**: `IrTemplateExpressions.render` (`src/addons/base/models/ir_template_expressions.py:958`) levanta a propósito |
| xmlid (`_xmlid_to_res_id`, `ref`) | presente, `src/addons/base/models/ir_model.py:3104-3135` |
| `mail.mt_note`, `mail.mt_comment` | sembrados, `addons/mail/migrations/0002_seed_message_subtypes.py:23` |
| vista `track_po_line_qty_received_template` | ausente: `addons/purchase` no tiene `data/` |
| `mail.compose.message`, `_action_send_mail` | no medido |

Dependencias, en orden: (1) motor QWeb `ir.qweb._render`; (2) carga de
`<template>` como `ir.ui.view` con xmlid; (3) `MailRenderMixin`; (4)
`_get_source_from_ref`; (5) `message_post` compatible (`subtype_id`, kwargs,
`_raise_for_invalid_parameters`); (6) rama plantilla (`mail.compose.message`);
(7) `_track_qty_received` y el gancho de `write` (`:316`).

**Lo que este hallazgo no cierra.** El motor QWeb no tiene unidad ni TASK en
`plan.jsonl` (búsqueda `qweb|ir_qweb|ir.qweb`: sólo la fila 274, que lo
consume). Sin él, un porte de `message_post_with_source` sólo podría entregar
la rama de plantilla o un cuerpo vacío, y las dos cosas están prohibidas
(stub, mensaje falso). Desenlace: DESCONOCIDO con condición de cierre —
que el ejecutor asigne al motor QWeb una unidad con TASK canónica (no se
inventa aquí). Mientras tanto `mail-message-post-with-source-0121` y
`purchase-line-track-qty-received-0122` siguen abiertas, bloqueadas por esa
pieza.

## B. Primitivas de recordset en `TimeStampedModel`/`Uom`

`Uom` → `TimeStampedModel` (`src/addons/base/models/timestamped_mixin.py:85`)
→ mixins → `django.db.models.Model`. `BaseModel` es `src/orm/models.py:6717-11072`.

| Primitiva | `odoo19c: odoo/orm/models.py` | `BaseModel` local | En `TimeStampedModel` |
|---|---|---|---|
| browse / ensure_one / ids | 5883 / 5931 / 5905 | 9491 / 9517 / 9509 | AUSENTE |
| `__bool__` / `__len__` / `__iter__` / `__contains__` | 6475 / 6479 / 6483 / 6525 | 9539 / 9543 / 9653 / 9673 | AUSENTE (`bool` de Django: siempre `True`) |
| `__or__` / `__and__` / `__sub__` | 6587 / 6575 / 6563 | 10069 / 10055 / 10041 | AUSENTE |
| `__eq__` / `__hash__` | 6608 / 6662 | 9582 / 9578 | **los de Django**: por modelo y pk; `hash` levanta sin pk |
| filtered / mapped / sorted / grouped / exists | 6186 / 6120 / 6263 / 6218 / 5545 | 10154 / 10094 / 10212 / 10194 / 10695 | AUSENTE |
| with_context / with_env / sudo / with_company / env | 6021 / 5945 / 5954 / 5991 / 5878 | 9980 / 9929 / 9939 / 9958 / `__init__` | AUSENTE |
| invalidate_recordset / flush_recordset | 6724 / 6367 | ligadas cerca de 5798 | AUSENTE |
| read / unlink / copy / search | 3469 / 4194 / 5530 / 1363 | 7117 / 8883 / 9300 / 8921 | AUSENTE |
| write | 4334 | 10396 | sustituto Django en `RecordLoaderMixin.write` (`models.py:3012`), no es el `write` de recordset |
| `_compute_display_name` | 1425 | 4664 | PRESENTE vía `DisplayNameMixin` |

`odoo19c: addons/uom/models/uom_uom.py` usa `self.env` (:66,:119),
`ensure_one` (:118,:129,:135,:164,:183,:197,:220-221), `ids` (:209), `mapped`
(:111), `browse` (:214,:216), `sudo().search` (:207) e `if not self` en
`_compute_quantity`. El `Uom` local no invoca ninguna sobre una instancia, y
el barrido por regex de `addons/*/models` no encontró llamadas de primitiva
sobre un `Uom` (cota inferior: regex, no auditoría).

**Obligaciones no verificadas, conservadas.** Cada primitiva AUSENTE de la
tabla, aplicada a `uom.uom`, sigue siendo obligación no verificada: no se ha
demostrado su equivalencia contractual sobre una instancia de Django. El plan
no tiene unidad que migre `Uom` a `BaseModel` (patrón existente:
`(models.BaseModel, TimeStampedModel)`, p. ej. `designs/purchase-order-header.md:12`).
Su apertura es decisión del ejecutor.
