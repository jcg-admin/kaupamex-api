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
