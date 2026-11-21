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
quedan como están. Los otros 27 asignan, y son los que el ORM despacha: los
23 de `compute='_compute_…'`, `_check_won_validity` y los onchanges
`_onchange_commercial_partner_id` y `_onchange_phone_validation`, más
`_compute_team_id`… (la lista exacta la produce el AST, abajo).

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
