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

## La causa compartida y los nueve modelos (2026-11-12)

### Cómo recibe su identidad un modelo, en la fuente y aquí

En la fuente la identidad la decide el metaclase de modelos: una clase con
`_name` propio define un modelo; una sin `_name` y con un solo `_inherit`
**extiende** ese modelo, no crea otro (`odoo19c: odoo/orm/model_classes.py`,
`_init_model_class_attributes` y el armado de la clase de registro). Un
atributo de clase de Python nunca convierte en mixin la identidad de otro
modelo: cada modelo del registro se arma desde sus definiciones.

Aquí la clase la construye `ModelBase` de Django y la herencia es la de
Python: `_name` declarado en `MailThread` llega por MRO a toda clase concreta
que no declare el suyo.

Lo medido sobre quién lee el nombre:

| Lector | Cómo lee | Con nombre heredado |
|---|---|---|
| `orm.registry._register` | `model.__dict__.get('_name')` | no registra la clase (correcto) |
| `_wants_log_access` (inyección DEC-09) | `__dict__` | no inyecta (el defecto de la cuenta analítica) |
| 73 lecturas en `src/orm` | `getattr(model, '_name', …)` / atributo | devuelven `'mail.thread'` |

Varias de esas 73 ya caen a `model._meta.label_lower` cuando el nombre es
falso (`orm/models.py:273`, `:4100`, `environments.py:2177`): el nombre
heredado les impide caer al propio.

### Corrección de la causa: fallar al preparar, no ocultar

Censo por AST de las lecturas de `_name` en `src/orm`
(`outputs/name-reads-src-orm-20261112.tsv`): **98**, de ellas 70 por
atributo, 23 por `getattr` y 5 por `__dict__` (la cifra de 73 de arriba era
de una búsqueda por regex y queda corregida).

Momento de cada una, medido sobre su función y sus llamadores:

- ninguna corre durante la construcción de la clase por `ModelBase`;
- las dos de nivel de módulo (`fields_relational.py:2850-2853`) son
  `property` perezosas de `ForeignObjectRel`;
- `_check_model_extension` y `_check_model_parent_extension` corren desde
  `ensure_model_class_attributes`, en `base.apps.ready()` (`apps.py:96`),
  tras todo `class_prepared`;
- el resto es de ejecución (recordsets, `create`, `write`, exportación).

Con los nueve modelos ya declarando su nombre, un receptor que pusiera
`_name = None` no cambiaría ningún modelo vivo: su único efecto sería
**ocultar** el siguiente caso. Se descarta. La corrección de la causa es
fallar en `class_prepared`: un modelo concreto, no proxy, del registro vivo
de apps, que hereda un `_name` sin declarar el suyo lanza
`ImproperlyConfigured` nombrando el nombre heredado. Igual que la fuente,
donde un modelo nunca nace con la identidad de un mixin, no se crea una
segunda autoridad: el `_name` declarado sigue siendo la única. Quedan fuera,
por construcción, los modelos históricos (`_meta.apps` no es el registro
vivo), los proxy (comparten identidad) y los de terceros (no heredan
`_name`).

### Los nueve modelos

Ninguno necesita migración: los nueve heredan `TimeStampedModel` y tienen ya
las cuatro columnas en modelo y tabla (medido por `information_schema`).

| Modelo | Identidad declarada | Origen |
|---|---|---|
| `base_automation.BaseAutomation` | `base.automation` | `base_automation.py:125-127` |
| `fleet.FleetVehicleModel` | `fleet.vehicle.model` | `fleet_vehicle_model.py:23-26` |
| `fleet.FleetVehicle` | `fleet.vehicle` | `fleet_vehicle.py:24-28` |
| `fleet.FleetVehicleLogContract` | `fleet.vehicle.log.contract` | `fleet_vehicle_log_contract.py:10-13` |
| `fleet.FleetVehicleLogServices` | `fleet.vehicle.log.services` | `fleet_vehicle_log_services.py:9-12` |
| `mass_mailing.MailingMailing` | `mailing.mailing` | `mailing.py:38-49` |
| `website.StaticPage` | `settings.static.page` | propio: su tabla |
| `stock.ReturnRequest` | `return.request` | propio: su tabla |
| `helpdesk.SupportTicket` | `support.ticket` | propio: su tabla |

Los seis con contraparte llevan todos los atributos de su cabecera, verbatim.
Los tres propios derivan el nombre de su tabla, que es la identidad que
`check_table_matches_name` ya exige (`_table == _name.replace('.', '_')`), y
declaran el `_inherit` de los mixins que heredan. La sección «Lo que este
diseño no cierra» de arriba queda cerrada por esta decisión.
