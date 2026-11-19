# `mass_mailing` sobre `BaseModel`, con sus cabeceras y su seguridad

Unidad hija `basemodel-adoption-mass-mailing-0397` del paraguas
`basemodel-adoption-0397` (TASK-API-0397), con la forma de
`basemodel-adoption-fleet.md`. Cierra la condición «needs headers» que
mantenía `mass_mailing` en `PENDING`.

## Contrato medido en la referencia

Cinco modelos de `odoo19c: addons/mass_mailing/models/` tienen puerto.
`mailing.mailing` ya declara su cabecera (`mailing.py:36-46`). Los otros
cuatro no declaraban ningún atributo de clase de modelo; la fuente declara:

| Modelo | Fuente | `_description` | `_order` | otros |
|---|---|---|---|---|
| `mailing.contact` | `mailing_contact.py:14-17` | `Mailing Contact` | `name ASC, id DESC` | `_inherit = ['mail.thread.blacklist', 'properties.base.definition.mixin']` |
| `mailing.list` | `mailing_list.py:12-18` | `Mailing List` | `create_date DESC` (la fuente asigna `_order` dos veces; gana la segunda) | `_mailing_enabled = True`, `_disable_data_merge = True` |
| `mailing.subscription` | `mailing_subscription.py:11-15` | `Mailing List Subscription` | `list_id DESC, contact_id DESC` | `_table = 'mailing_subscription'`, `_rec_name = 'contact_id'` |
| `mailing.trace` | `mailing_trace.py:54-57` | `Mailing Statistics` | `create_date DESC` | `_rec_name = 'id'` |

Las tablas ya coinciden con `_name` (`Meta.db_table`).

Seguridad (`odoo19c: addons/mass_mailing/__manifest__.py:21-25`):
`data/res_groups_privilege_data.xml` (el privilegio),
`security/res_groups_data.xml` (dos grupos), `security/security.xml` (una
regla) y `security/ir.model.access.csv` (25 filas).

## Cambios

1. Los cuatro modelos declaran su cabecera verbatim y los cinco derivan de
   `models.BaseModel`.
2. `MailingSubscription.list_id` ≙ `list_id`
   (`odoo19c: addons/mass_mailing/models/mailing_subscription.py:18`): el
   campo se llamaba `mailing_list`, y el `_order` de la fuente lo nombra. La
   migración `0006_mailingsubscription_list_id` renombra campo y columna
   (forma C, `db_column='list_id'`) y conserva las filas; la restricción
   única se rehace sobre el nombre nuevo. Consumidores: `services.py` y dos
   archivos de prueba.
3. Seguridad, copia fiel en `data` del manifiesto y en su orden, sin los
   registros cuyo destino no tiene puerto: `user_ids` del grupo (como
   `purchase-security.md`), la regla sobre `properties.base.definition`
   (filtra por `mailing.contact.properties`, campo de un mixin sin puerto) y
   11 filas del CSV. Quedan 14 filas. Las omisiones se declaran en el
   manifiesto con su sucesor.
4. `test_mass_mailing_models.py`: los inversos pasan a recordset (`in`).
5. `test_basemodel_reach.py`: `mass_mailing` sale de `PENDING`.

## Fuera de esta unidad, con su sucesor

- Registros de modelos sin puerto y la regla de propiedades —
  `mass-mailing-report-models-0397`.
- Nombres de campo de la fuente que este puerto aún difiere (`user` ≙
  `user_id`, `contact_lists` ≙ `contact_list_ids`, `mailing` ≙
  `mass_mailing_id` y `contact` en `mailing.trace`) y los objetos de tabla
  (`_unique_contact_list`, `_check_res_id_is_set`, `_percentage_valid`,
  `_email_from`; el `unique_mailing_trace` propio que la fuente no tiene) —
  `mass-mailing-field-names-0397`.

## Pruebas

`tests/unit/mass_mailing/test_mass_mailing_basemodel.py`: los cinco modelos
son `BaseModel`; las cuatro cabeceras; privilegio y grupos cargados; 14 filas
de ACL; el orden por `list_id` sigue el `_order` del comodelo invertido
(`odoo19c: odoo/orm/models.py:5296-5310`), con su control de fechas
cambiadas; un usuario interno sin grupo no lee una lista. Control de
anulación: sin el `_order` caen la cabecera y el orden, y nada más.
