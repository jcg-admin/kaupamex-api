# `mail.activity` y `mail.activity.type` sobre `BaseModel`, con su ACL

Unidad hija `basemodel-adoption-mail-activity-0397` del paraguas
`basemodel-adoption-0397` (TASK-API-0397).

## Contrato medido en la referencia

- `mail.activity` (`odoo19c: addons/mail/models/mail_activity.py`) y
  `mail.activity.type` (`odoo19c: addons/mail/models/mail_activity_type.py`).
- `odoo19c: addons/mail/security/ir.model.access.csv`: 69 filas.

## Medido en este árbol

- De las 69 filas, resuelven 4: las tres de los dos modelos y la de
  `base.ir_actions_report`. El cargador nombró los 42 modelos que no
  resuelven: sin puerto (`discuss.*`, `mail.push`, `mail.guest`,
  `fetchmail.server`…) o sin cabecera de la fuente (`mail.message`,
  `mail.mail`, `mail.followers`, `mail.template`…).
- `mail.activity.mixin` es abstracto: el trinquete de
  `test_basemodel_reach.py` no lo mide, y con los dos modelos concretos
  adoptados `mail` sale de `PENDING`. Adoptar el mixin convertiría en
  `BaseModel` a `crm.lead`, `sale.order`, `stock.lot`, `stock.picking` y
  `support.ticket` (medido por AST), que no lo son: espera a esas apps.
- Los consumidores leen las actividades con `objects`
  (`_activity_queryset` de `mail_activity_mixin.py`), que no cambia.

## Cambios

1. `MailActivity` y `MailActivityType` derivan de
   `(models.BaseModel, TimeStampedModel)`.
2. `addons/mail/security/ir.model.access.csv` con las 4 filas que resuelven,
   en `data` del manifiesto tras los grupos; las 65 restantes se declaran en
   el manifiesto.
3. `test_basemodel_reach.py`: `mail` sale de `PENDING`.

## Fuera de esta unidad, con su sucesor

- Las 65 filas — `mail-model-headers-0397`.
- `mail.activity.mixin` sobre `BaseModel` — `mail-activity-mixin-0397`,
  después de las adopciones de `crm`, `sale`, `stock` y `helpdesk`.

## Pruebas

`tests/unit/mail/test_mail_activity_basemodel.py`: los dos modelos son
`BaseModel`; las 4 filas; un usuario interno lee y no escribe un tipo de
actividad. Anulación: sin el cambio de bases caen 3 de las 4.
