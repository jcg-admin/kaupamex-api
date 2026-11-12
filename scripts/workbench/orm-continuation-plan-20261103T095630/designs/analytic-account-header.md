# Cabecera de `account.analytic.account` y nombres heredados de un mixin

## Lo medido

`AccountAnalyticAccount._name` valía `'mail.thread'`: la clase hereda de
`MailThread` y no declaraba el suyo. Consecuencias, cada una medida:

- `model_by_name('account.analytic.account')` devolvía `None`;
- la inyección del log-access (DEC-09) no la alcanzaba: la tabla no tenía
  `create_date`, `write_date`, `create_uid` ni `write_uid`;
- de los siete atributos de clase de la fuente
  (`odoo19c: addons/analytic/models/analytic_account.py:11-18`, odoo-tools
  `abe4040ec1`) no había ninguno.

## Corrección

Los siete atributos, verbatim, y la migración
`analytic/0011_log_access_auto_injection.py` con las cuatro columnas de la
metaclase (`odoo19c: odoo/orm/models.py:287-292`) y sus nombres de la
fuente. Escrita a mano porque `makemigrations --noinput` no añade un
`auto_now_add` sin valor por defecto; `makemigrations --check` confirma que
coincide con el modelo.

## El mismo defecto en otros nueve modelos

`tests/unit/orm/test_model_names_are_declared.py` recorre todo modelo
concreto con `_name` y exige que lo declare. Nueve lo heredan hoy y quedan
en `xfail` estricto con el origen de su cabecera:

| Modelo | `_name` heredado | Cabecera |
|---|---|---|
| `base_automation.BaseAutomation` | `mail.thread` | `addons/base_automation/models/base_automation.py` |
| `fleet.FleetVehicleModel` | `mail.thread` | `addons/fleet/models/fleet_vehicle_model.py` |
| `fleet.FleetVehicle` | `mail.thread` | `addons/fleet/models/fleet_vehicle.py` |
| `fleet.FleetVehicleLogContract` | `mail.thread` | `addons/fleet/models/fleet_vehicle_log_contract.py` |
| `fleet.FleetVehicleLogServices` | `mail.thread` | `addons/fleet/models/fleet_vehicle_log_services.py` |
| `mass_mailing.MailingMailing` | `mail.thread` | `addons/mass_mailing/models/mailing.py` |
| `website.StaticPage` | `website.searchable.mixin` | propio del L0 |
| `stock.ReturnRequest` | `mail.thread` | propio del L0 |
| `helpdesk.SupportTicket` | `mail.thread` | propio del L0 |

Los seis con contraparte siguen el mismo patrón: cabecera de la fuente y
migración de log-access, por tramos.

**Lo que este diseño no cierra.** Los tres modelos propios del L0: la regla
de atributos de clase prohíbe inventar una cabecera donde la fuente no la
tiene, pero el nombre heredado es incorrecto igual. Condición de cierre:
decidir si un modelo propio que hereda `mail.thread` lleva un `_name`
propio (lo exige `model_by_name` y el log-access) o si `_name` deja de
heredarse a clases concretas en el ORM. Hasta entonces quedan en `xfail`.

## Verificación

- RED: `model_by_name` daba `None`; `_name` era `'mail.thread'`.
- GREEN: cabecera 3 passed; `tests/unit/account`, `tests/unit/analytic` y la
  prueba de unidad C: 679 passed (`-n 4`); compuerta: 212 passed, 9 xfailed.
- Anulación (retirar `_name`): caen exactamente los 3 casos que dependen de
  él; el de la tabla sobrevive por su `db_table` explícito.
