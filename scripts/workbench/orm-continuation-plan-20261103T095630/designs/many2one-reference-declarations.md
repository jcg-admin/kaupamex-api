# Diseño: las declaraciones `Many2oneReference` de la fuente

Unidad `many2one-reference-declarations-0397`.

## Contrato medido en la referencia

`fields.Many2oneReference` aparece en 12 declaraciones de `odoo19c` fuera de
pruebas. Seis tienen modelo en este árbol y aquí se declaran `fields.Integer`:

| Modelo | Campo | `model_field` | Fuente |
|---|---|---|---|
| `ir.attachment` | `res_id` | `res_model` | `odoo19c: odoo/addons/base/models/ir_attachment.py:458` |
| `ir.model.data` | `res_id` | `model` | `odoo19c: odoo/addons/base/models/ir_model.py:2240` |
| `mail.message` | `res_id` | `model` | `odoo19c: addons/mail/models/mail_message.py:114` |
| `mail.activity` | `res_id` | `res_model` | `odoo19c: addons/mail/models/mail_activity.py:60` |
| `mail.followers` | `res_id` | `res_model` | `odoo19c: addons/mail/models/mail_followers.py:29` |
| `base.automation` | `trg_field_ref` | `trg_field_ref_model_name` | `odoo19c: addons/base_automation/models/base_automation.py:192` |

Las otras seis (`rating`, `mail.scheduled.message`, `loyalty.history`,
`card.card`, `calendar.event`, `mailing.trace`) no tienen modelo aquí o, en
`mailing.trace`, no tienen el campo: llegan con su porte.

## Dónde engancha aquí

`Many2oneReference` (`src/orm/fields_reference.py`) es un `IntegerField` cuyo
`deconstruct` publica la ruta de `IntegerField`: cambiar la declaración no
mueve la columna ni genera migración. Lo que cambia es el tipo del campo
(`type = 'many2one_reference'`, `ttype` en `ir.model.fields`), `model_field`
y la conversión de un registro a su id en `convert_to_cache`.

## La prosa heredada que esta unidad corrige

Los `help_text` de `ir.attachment`, `mail.message`, `mail.activity` y
`mail.followers` decían «Integer plano» o «el ORM shim no tiene un tipo
Many2oneReference fiel»; las dos afirmaciones dejan de ser ciertas. El texto
de ayuda está en el estado de migración, así que su corrección lleva las
migraciones `0125_irattachment_res_id_help_text` (base) y
`0013_res_id_help_text` (mail), que sólo cambian ese texto: ni la columna ni
su tipo se mueven.

## Fuera de esta unidad

`_update_inverses` y `_record_ids_per_res_model` (`:89-118`) siguen sin
consumidor: ningún `One2many` del árbol tiene un `Many2oneReference` por
inverso (`message_ids` de `mail.thread` es aquí una propiedad, no un
`One2many`).

## Pruebas

`tests/unit/orm/test_many2one_reference_declarations.py`: cada uno de los seis
campos es `Many2oneReference` con el `model_field` de la fuente, y
`makemigrations --check` sigue limpio.
