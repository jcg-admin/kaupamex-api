# Los contactos de la regla de conciliación apuntan a `res.partner`

Fecha: 2026-11-24T08:40:20. TASK-API-0397, unidad sucesora
`account-reconcile-partner-comodel-0397`, registrada en
`designs/account-basemodel-u5.md`.

Referencia (Odoo 19 Community):
odoo19c: addons/account/models/account_reconcile_model.py:20-23 —
`partner_id = fields.Many2one(comodel_name='res.partner')` en la línea;
odoo19c: addons/account/models/account_reconcile_model.py:118-122 —
`mapped_partner_id`, `comodel_name='res.partner'`;
odoo19c: addons/account/models/account_reconcile_model.py:144-145 —
`match_partner_ids = fields.Many2many('res.partner')`.

## El estado heredado

Los tres campos se declaran sobre `settings.AUTH_USER_MODEL`. Un usuario
no es un contacto: la fuente modela `res.users` con
`_inherits = {'res.partner': 'partner_id'}`, así que un proveedor o un
banco sin cuenta de acceso no se puede elegir como contacto de la regla.
El resto de `account` ya apunta a `'base.ResPartner'`
(`account_move.py:238`, `account_journal.py:132`,
`account_bank_statement_line.py:150`).

## Qué cambia

1. `AccountReconcileModelLine.partner` y `AccountReconcileModel.mapped_partner`
   pasan a `'base.ResPartner'`, con `on_delete=SET_NULL` y `null=True`
   como hoy.
2. `AccountReconcileModel.match_partner_ids` pasa a `'base.ResPartner'`.
3. Migración `addons/account/migrations/0054_reconcile_partner_comodel.py`:
   - las dos Many2one: se retiran las restricciones de clave foránea, se
     traduce cada id de usuario al `partner_id` de ese usuario
     (`UPDATE … FROM res_users`) y se altera el campo;
   - la Many2many: Django no altera el destino de una Many2many, así que se
     añade el campo nuevo, se copian las filas traduciendo el id por el
     `partner_id` del usuario, y se retira el viejo con su tabla.
   Una fila cuyo usuario ya no exista queda en NULL (la Many2one) o se
   descarta (la Many2many): es lo mismo que `SET_NULL` habría hecho.

## Pruebas

`tests/unit/account/test_account_reconcile_partner_comodel.py`:

- `test_the_line_partner_is_a_res_partner`;
- `test_a_contact_without_login_can_map_the_partner` — un `ResPartner` sin
  usuario fija el partner propuesto con `compute_mapped_partner`;
- `test_the_rule_restricts_to_res_partners` — `match_partner_ids` acepta un
  `ResPartner` y `compute_can_be_proposed` lo cuenta.

Anulación: con `partner` de vuelta en `AUTH_USER_MODEL` caen el primero y el
segundo; el tercero depende sólo de `match_partner_ids`.

## Citas de la fuente por archivo

- `addons/account/models/account_reconcile_model.py`: odoo19c: addons/account/models/account_reconcile_model.py:20-23,
  odoo19c: addons/account/models/account_reconcile_model.py:118-122 y
  odoo19c: addons/account/models/account_reconcile_model.py:144-145.

## Símbolos tocados por archivo

- `addons/account/models/account_reconcile_model.py`: `AccountReconcileModel`, `AccountReconcileModelLine`.
- `addons/account/migrations/0054_reconcile_partner_comodel.py`: `Migration`.

## Lo que este corte no cierra

Nada propio de la unidad.
