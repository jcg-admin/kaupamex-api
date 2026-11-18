# `mail/data/mail_groups.xml`: los grupos de `mail`

Creado: 2026-11-18T21:40:51 (UTC). TASK-API-0397, ítem del plan
`mail-groups-data-0397`. Referencia: odoo-tools `abe4040ec1`, Odoo 19
Community, LGPL-3: copia con adaptación y atribución. Prerrequisito de
`basemodel-adoption-helpdesk.md`.

Símbolo: `mail.group_mail_canned_response_admin` (y los demás registros de
`odoo19c: addons/mail/data/mail_groups.xml`).

## La prosa heredada, validada

| Afirmación | Medido | Veredicto |
|---|---|---|
| «la seguridad de `mail` no está portada y ese grupo no existe en este árbol» (`sales_team_security.xml`, comentario de cabecera, punto 1) | `ir_model_data` de `orm_x2hokp_qa`: ningún `mail.group_mail_canned_response_admin`; el manifiesto de `mail` no declara `data` | **cierto**, pero es un porte pendiente y no un bloqueo: las referencias del archivo (`base.module_category_marketing`, `base.group_system`) existen en la base |

## La fuente

`odoo19c: addons/mail/data/mail_groups.xml` (en `data` del manifiesto,
`odoo19c: addons/mail/__manifest__.py:64`), todo bajo `noupdate="1"`:

1. el privilegio `res_groups_privilege_canned_response` (secuencia 100,
   categoría `base.module_category_marketing`);
2. `group_mail_canned_response_admin`, con ese privilegio;
3. `group_mail_template_editor`;
4. `base.group_system` implica a los dos grupos anteriores;
5. `group_mail_notification_type_inbox`.

## Decisión

- Copia fiel del archivo en `addons/mail/data/mail_groups.xml`, con
  atribución, cargada por el `data` del manifiesto de `mail`.
- `sales_team_security.xml`: `group_sale_manager` recupera la implicación
  de `mail.group_mail_canned_response_admin`, como en la fuente
  (`odoo19c: addons/sales_team/security/sales_team_security.xml:30`). Se
  retira el punto 1 de la cabecera. El punto 2 (`base.user_admin`) sigue,
  porque es la decisión DEC-3: el usuario inicial lo crea
  `kaupamex-bin company_create`.

## RED

Cargando los datos con `load_data` en `mode='init'`, el paso real de la
instalación:

1. los cuatro registros existen con sus xmlid y el privilegio tiene su
   categoría y secuencia;
2. `base.group_system` implica `group_mail_template_editor` y
   `group_mail_canned_response_admin`;
3. `sales_team.group_sale_manager` implica
   `group_mail_canned_response_admin`.
