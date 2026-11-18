# Porte completo de `helpdesk` desde Odoo 19 Enterprise

Referencia: `odoo19e: helpdesk`, licencia `OEEL-1` (manifiesto). Mecanismo:
reimplementación nativa del patrón y del contrato, sin copiar el texto
(`porte-completo-no-parcial.md`, «La licencia cambia el MECANISMO»).

## La prosa heredada, validada

| Afirmación | Medido | Veredicto |
|---|---|---|
| `support.ticket` es un modelo propio sin contraparte (censo de `basemodel-counterpart-census.tsv`) | el censo sólo miró `odoo19c`; `odoo19e: helpdesk/models/helpdesk_ticket.py` declara `helpdesk.ticket` | **falso**: la contraparte existe en Enterprise. Corrección del ejecutor del 2026-11-18 |

## Inventario de la referencia (medido)

| Archivo | Líneas | `def` | campos |
|---|---|---|---|
| `helpdesk_tag.py` (`helpdesk.tag`) | 30 | 2 | 2 |
| `helpdesk_tag_assignment.py` (`helpdesk.tag.assignment`) | 16 | 0 | 3 |
| `helpdesk_stage.py` (`helpdesk.stage`) | 112 | 6 | 13 |
| `helpdesk_sla.py` (`helpdesk.sla`) | 78 | 5 | 12 |
| `helpdesk_sla_status.py` (`helpdesk.sla.status`) | 136 | 6 | 9 |
| `helpdesk_team.py` (`helpdesk.team`) | 1000 | 71 | 54 |
| `helpdesk_ticket.py` (`helpdesk.ticket`) | 1070 | 66 | 72 |

Hay además extensiones (`_inherit`) de `digest.digest`, `ir.module.module`,
`ir.ui.menu`, `mail.message`, `rating.rating`, `res.company`, `res.partner` y
`res.users`. Los datos: 25 entradas en `data`, que incluyen la seguridad
(`helpdesk_security.xml` y el CSV), una secuencia, un cron, plantillas de
correo, subtipos y el digest.

Dependencias: `base_setup`, `mail`, `utm`, `rating`, `web_tour`, `web_cohort`,
`resource`, `portal` y `digest`. Faltan en este árbol `web_tour` y
`web_cohort`, que sólo aportan cliente web (recorrido y vista de cohorte). Su
ausencia no bloquea los modelos. El manifiesto las declara igual; queda
registrado como DESCONOCIDO, con la condición de cierre de que exista el addon.

## Orden de unidades (dependencia de modelo, medida)

Relacionales medidos con `grep -nE "fields\.(Many2one|Many2many|One2many)\("`:
`helpdesk.stage.team_ids` → `helpdesk.team`; `helpdesk.sla` → `team`,
`stage`, `tag`; `helpdesk.sla.status.ticket_id` → `helpdesk.ticket`;
`helpdesk.tag.assignment.team_id` → `helpdesk.team`. `team`, `stage` y
`ticket` se referencian entre sí, así que ninguno se migra sin los demás.

1. `helpdesk.tag` (sin dependencias) y los grupos de `helpdesk_security.xml`
   con las filas del CSV que tocan a la etiqueta.
2. El esquema del núcleo, que va junto porque forma un ciclo: `team`, `stage`,
   `ticket`, `sla`, `sla.status` y `tag.assignment`, todos sus campos, sus
   restricciones, el CSV completo y las reglas de registro.
3. Los métodos de `team` y `ticket` por familias (alias y asignación, SLA,
   métricas, correo), cada familia una unidad con su RED.
4. El traslado de `support.ticket` y `support.ticket.reply` a
   `helpdesk.ticket`, con sus consumidores. Consumidores medidos con
   `grep -rln "support.ticket\|support_ticket" --include=*.py`:
   `seed_menu.py`, `mail/models/notification_emails.py`, la migración 0009
   de mail y siete pruebas.
5. Las extensiones `_inherit`, los datos y el cron.

## Prerrequisitos medidos (referencias de `helpdesk_security.xml`)

| Referencia | En la fuente | Aquí | Unidad previa |
|---|---|---|---|
| `base.module_category_services` | `odoo19c: odoo/addons/base/data/ir_module_category_data.xml:100` | lo deriva la migración 0090 de la ruta `category` del manifiesto; **se verifica en la base** | ninguna, si existe |
| `base.user_admin` | `odoo19c: odoo/addons/base/data/res_users_data.xml:14` | `res_users_data.py` sólo siembra `user_root` y `public_user` | sembrar `user_admin` en `base` |
| `mail.group_mail_canned_response_admin` | `odoo19c: addons/mail/data/mail_groups.xml:10` | `mail_groups.xml` no se carga; `mail.canned.response` no está portado (0 hits) | portar `mail_groups.xml` |

Sin esas filas, `helpdesk_security.xml` no se carga tal cual: `ref()` falla.
Adaptar el XML para esquivarlas sería una divergencia en lugar de un porte,
así que cada una entra antes como unidad propia.

Cada familia de métodos que todavía no se porta se declara con su bloqueo
medido (el modelo que le falta) y su sucesor, que es la unidad siguiente.
Nunca se omite en silencio.

Cada unidad se porta completa (todos sus símbolos), con RED, anulación y F2
propios. Ninguna declara divergencia en sustitución del porte.

## Lo que este diseño no cierra

Qué hacer con los campos propios de `support.ticket` sin contraparte en
`helpdesk.ticket` (`Category`, el endpoint `v2`). Se decide en la unidad 5,
midiendo el contrato de `tests/integration/helpdesk/test_support_endpoints.py`.
El sucesor queda bajo TASK-API-0397.
