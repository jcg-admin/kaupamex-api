# `fleet` sobre `BaseModel`, con sus cabeceras y su seguridad

Unidad hija `basemodel-adoption-fleet-0397` del paraguas
`basemodel-adoption-0397` (TASK-API-0397), con la forma de
`basemodel-adoption-purchase-requisition.md`.

## Contrato medido en la referencia

Once modelos en `odoo19c: addons/fleet/models/`. Cuatro tienen aquí su
cabecera (`fleet.vehicle`, `fleet.vehicle.model`, `fleet.vehicle.log.contract`,
`fleet.vehicle.log.services`). Siete no declaran ningún atributo de clase de
modelo, y la fuente declara (`atributos-de-clase-de-modelo.md`):

| Modelo | Fuente | `_description` | `_order` |
|---|---|---|---|
| `fleet.service.type` | `fleet_service_type.py:8-10` | `Fleet Service Type` | `name` |
| `fleet.vehicle.assignation.log` | `fleet_vehicle_assignation_log.py:8-10` | `Drivers history on a vehicle` | `create_date desc, date_start desc` |
| `fleet.vehicle.model.brand` | `fleet_vehicle_model_brand.py:8-10` | `Brand of the vehicle` | `name asc` |
| `fleet.vehicle.model.category` | `fleet_vehicle_model_category.py:8-10` | `Category of the model` | `sequence asc, id asc` |
| `fleet.vehicle.odometer` | `fleet_vehicle_odometer.py:8-10` | `Odometer log for a vehicle` | `date desc` |
| `fleet.vehicle.state` | `fleet_vehicle_state.py:8-10` | `Vehicle Status` | `sequence asc` |
| `fleet.vehicle.tag` | `fleet_vehicle_tag.py:8-9` | `Vehicle Tag` | — |

Seguridad (`odoo19c: addons/fleet/__manifest__.py:31-33`):
`security/fleet_security.xml` (el privilegio, `fleet_group_user`,
`fleet_group_manager` y nueve reglas) y `security/ir.model.access.csv` (24
filas).

## Cambios

1. Los siete modelos declaran su `_name`, `_description` y `_order`
   verbatim (`odoo19c: addons/fleet/models/fleet_vehicle_tag.py:8`, y los demás
   de la tabla).
2. Los once modelos derivan de `models.BaseModel`.
3. `addons/fleet/security/`: el XML y el CSV, copia fiel, en `data` del
   manifiesto en el orden de la fuente, sin los registros cuyo modelo no
   tiene puerto en este árbol (`fleet.vehicle.cost.report`,
   `fleet.vehicle.odometer.report`, `fleet.vehicle.send.mail` y la fila de
   `mail.activity.type`, que aún no es `BaseModel`). Se declaran en el
   manifiesto con su sucesor.
4. Consumidores del API de gestor sobre accesores que pasan a recordset, los
   que la suite derivada destape.
5. `test_basemodel_reach.py`: `fleet` sale de `PENDING`.

## Fuera de esta unidad, con su sucesor

- Los objetos de tabla de la fuente (`_name_uniq`, `_fleet_state_name_unique`)
  — `fleet-table-objects-0397`.
- Los registros de modelos sin puerto — `fleet-report-models-0397`.

## Pruebas

`tests/unit/fleet/test_fleet_basemodel.py`: los once modelos son `BaseModel`
con su `_description`; las filas del CSV que resuelven; los grupos y las
reglas del XML que resuelven; un usuario interno sin grupo de flota no lee
un vehículo.
