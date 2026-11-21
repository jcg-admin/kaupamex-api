# crm-lead-recordset-computes-0397 — cómputos de `crm.lead` sobre recordsets

Medido con AST sobre `addons/crm/models/crm_lead.py`: los 37 métodos con
`@api.depends`, `@api.constrains` u `@api.onchange` de `CrmLead` no iteran
`for lead in self`; están escritos para un solo registro, como declara el
comentario del bloque («aquí una instancia **es** un registro»). La fuente
declara 39 y todos iteran (`odoo19c: addons/crm/models/crm_lead.py`).

`_validate_fields` (`src/orm/models.py`) invoca cada restricción con el
recordset entero, como la fuente (`check(self)`), así que una alta de dos
iniciativas muere en `_check_won_validity` con `Expected singleton`
(reproducido en la porción `crm` de `basemodel-reverse-queryset-0397`).
Queda por medir cómo se despachan los cómputos y los onchanges: en esa
misma alta no fallaron, lo que apunta a un despacho por registro.

## Medido: también los cómputos

`_compute_field_value` (`src/orm/models.py`) llama `determine(field.compute,
self)` con el recordset, igual que la fuente. Sondeado: sobre dos
iniciativas, `write` de `partner_name`, `email_from`, `expected_revenue` o
`probability` y un `create` de dos mueren con `Expected singleton`. Todo
`write` o alta de más de una iniciativa falla.

## Alcance

De los 37 métodos decorados, 10 devuelven un valor: respaldan propiedades
de un solo registro (`_compute_user_company_ids`, `_compute_company_currency`,
`_compute_commercial_partner_id`, `_compute_lang_active_count`,
`_compute_is_automated_probability`, `_compute_meeting_display`,
`_compute_potential_lead_duplicates`, `_compute_partner_email_update`,
`_compute_partner_phone_update`, `_compute_is_partner_visible`). Ningún campo
los declara con `compute=`, así que el ORM no los invoca con recordsets;
quedan como están. Los otros 27 asignan, y son los que el ORM despacha:
los cómputos de campo, `_check_won_validity` y los dos onchanges. La lista
exacta, con los inversos que se sumaron al ejecutar, está en «Símbolos».

## Cambio

Cada uno de los 27 pasa a `for lead in self:` con su cuerpo sobre `lead`,
que es la forma de la fuente (`odoo19c: addons/crm/models/crm_lead.py`, cada
`_compute_*` itera `for lead in self`). El docstring queda fuera del bucle;
un `return` sin valor pasa a `continue`; `super()` no se toca. La lógica de
cada cuerpo no cambia: ya es la de un registro. El comentario del bloque que
declaraba «aquí una instancia **es** un registro» se reescribe.

Prueba: `tests/unit/crm/test_crm_lead_multi_record.py` —alta de dos y
`write` de dos para un campo de cada cómputo almacenado, y la restricción
sobre dos—, roja antes del cambio.

## Símbolos y lo que destapó la ejecución

Al ejecutar, los inversos `_inverse_email_from` y `_inverse_phone`
(`inverse='…'`, despachados por `determine_inverse` con el recordset)
fallaron igual y se suman. Los 29 métodos de `CrmLead` que cambian, medidos
por diferencia de AST contra el archivo anterior: `_check_won_validity`, `_compute_company_id`, `_compute_contact_name`, `_compute_date_last_stage_update`, `_compute_date_open`, `_compute_day_close`, `_compute_day_open`, `_compute_email_domain_criterion`, `_compute_email_from`, `_compute_email_state`, `_compute_function`, `_compute_lang_id`, `_compute_name`, `_compute_partner_address_values`, `_compute_partner_name`, `_compute_phone`, `_compute_phone_state`, `_compute_prorated_revenue`, `_compute_recurring_revenue_monthly`, `_compute_recurring_revenue_monthly_prorated`, `_compute_recurring_revenue_prorated`, `_compute_stage_id`, `_compute_team_id`, `_compute_website`, `_compute_won_status`, `_inverse_email_from`, `_inverse_phone`, `_onchange_commercial_partner_id`, `_onchange_phone_validation`.

Medido de paso, y no es de esta unidad: un `write` de `partner_name` sobre
una iniciativa sin cliente se pierde, también con un solo registro. El
cómputo lo vuelve a vaciar porque el `write` por fila no protege los campos
escritos frente al recálculo. Es el hueco que cubren las tareas abiertas del
ORM sobre `write` (anunciar los calculados escritos con `modified` y portar
`_write`/`_write_multi`). La prueba de esta unidad escribe `name` en su
lugar.
