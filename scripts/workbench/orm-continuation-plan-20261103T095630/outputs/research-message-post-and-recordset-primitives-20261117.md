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

Dependencias, en orden: (1) [descartado: QWeb no se porta, ver la corrección]; (2) un registro de
cuerpos por xmlid que sustituya a `ir.ui.view` (#279); (3) `MailRenderMixin` sin `ir.qweb`; (4)
`_get_source_from_ref`; (5) `message_post` compatible (`subtype_id`, kwargs,
`_raise_for_invalid_parameters`); (6) rama plantilla (`mail.compose.message`);
(7) `_track_qty_received` y el gancho de `write` (`:316`).

**Corrección (mismo día): QWeb NO se porta, y eso ya está decidido.** La
primera redacción de este párrafo declaraba el motor QWeb «sin unidad ni
TASK» y pedía al ejecutor una unidad para portarlo. Era falso: se buscó sólo
en `plan.jsonl` y no en el registro de gobierno. Lo destapó la pregunta del
ejecutor. Las decisiones vigentes son:

- `kaupamex-docs: gestion/pm/api/iniciativas/modulo-employee-management/decisiones-modulo-employee-management.rst`,
  **DEC-EM-01** (aprobada 2026-08-01): `web` se adapta a DRF + SPA React; el
  templating QWeb (`ir.ui.view`, `ir.qweb.field.*`) «React reemplaza»
  (`:110-111`; `analisis-web-nativo-drf-spa.rst:124-135`, «No aplica»).
- `.../alinear-arbol-addons-a-familias-odoo/decisiones-alinear-arbol-addons-a-familias-odoo.rst`,
  **DEC-AF-08** (`:361-403`): `views/` (plantillas QWeb) **no se porta**; su
  propia ceguera declarada (`:468-472`) es la lógica de negocio embebida en
  plantillas.
- `hallazgo-H-API-796` (`:86-91`): «QWeb no se porta: el contrato del backend
  es DRF + drf-spectacular y la vista la renderiza `ui`».
- Precedentes de porte del mismo caso: `hallazgo-H-API-775` (`:171-175`), el
  cuerpo de `mail.account_security_alert` va verbatim por `dispatch_email`; y
  `addons/stock/models/stock_move_line.py:239-245` (D-1), el mensaje de
  `stock.track_move_template` se arma igual y se devuelve como dict, con
  sucesor **#279** («quién lo publica es una decisión de la familia `mail`»).

Consecuencia para TASK-API-0121: el motor QWeb **no** es la dependencia. Lo
que se porta es el contrato de `message_post_with_source` —firma,
`_get_source_from_ref`, resolución de `subtype_xmlid` con `mail.mt_note` por
defecto, kwargs prohibidos, un `message_post` por registro— con la fuente de
tipo vista resuelta a un cuerpo producido sin QWeb, cuyo **contenido** es el
de la plantilla (DEC-AF-08 exige no perder la lógica que la plantilla lleva).
La forma de ese registro de cuerpos por xmlid es decisión de la familia
`mail` y ya tiene sucesor: **#279** (cita de ordinal heredada; su
`TASK-<CAPA>-NNNN` durable no se acuñó desde esta VM, que no escribe en el
TaskStore). Hasta resolverla, `mail-message-post-with-source-0121` y
`purchase-line-track-qty-received-0122` siguen abiertas; ningún stub ni
mensaje vacío.

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

## C. Reconciliación de la «#279» y mecanismo autorizado (2026-11-17, tercer pase)

Lectura del store en sólo lectura
(`thyrox/agent-results/agent_store.sqlite3`, tabla `tasks`): el ordinal
`279` nombra **tres** tareas distintas —`TASK-API-0153` (*«stock no declara
ningún ReportSpec propio»*), `TASK-GEN-0531` y `TASK-THYROX-0522`—, y
ninguna trata del chatter. La «tarea #279» de
`addons/stock/models/stock_move_line.py:239-245` (D-1) es una cita de ordinal
en colisión: no identifica un sucesor. La autoridad del mecanismo es
**TASK-API-0121** (fila 202, `in_progress`, *«Capa 0 · account, mail, stock,
web…»*), con la unidad `mail-message-post-with-source-0121` del plan.

Mecanismo autorizado (DEC-AF-08: se porta la responsabilidad, se sustituye el
sustrato de presentación), con precedentes implementados:

- `addons/crm/models/crm_lead.py:2081-2092`: «aquí no hay QWeb, así que el
  resumen se compone con el mismo contenido» y se publica con
  `message_post(body=…)`.
- `addons/base_install_request/wizard/base_module_install_request.py:101-107`:
  el cuerpo se compone en Python, «la vía "se construye"».
- `addons/base_install_request/data/__init__.py:8-35`: plantilla `mail.template`
  con sintaxis de Django, registrada por su xmlid.

Para `message_post_with_source`: la fuente de tipo vista se resuelve por su
xmlid a un constructor de cuerpo en Python, con el contenido de la plantilla;
la de tipo `mail.template`, por la ruta existente. Lo local que falta:
`subtype_xmlid`/`subtype_id` (hoy `message_post` acepta `subtype=` sin valor
por defecto), `_raise_for_invalid_parameters`, `_get_source_from_ref` y el
registro de constructores. `mail.compose.message` y `_action_send_mail` están
ausentes, así que la rama de plantilla del contrato de la fuente queda como
obligación abierta de TASK-API-0121, no se simula.
