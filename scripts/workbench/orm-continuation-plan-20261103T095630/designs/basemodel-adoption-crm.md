# `crm` sobre `BaseModel`, con su seguridad

Unidad hija `basemodel-adoption-crm-0397` del paraguas
`basemodel-adoption-0397` (TASK-API-0397), con la forma de
`basemodel-adoption-fleet.md`.

## Contrato medido en la referencia

Seis modelos de `odoo19c: addons/crm/models/` tienen puerto: `crm.lead`
(`crm_lead.py:84-97`), `crm.lead.scoring.frequency` y
`crm.lead.scoring.frequency.field` (`crm_lead_scoring_frequency.py:7-20`),
`crm.lost.reason` (`crm_lost_reason.py:7-9`), `crm.recurring.plan`
(`crm_recurring_plan.py:7-10`) y `crm.stage` (`crm_stage.py:14-23`). Sus
cabeceras ya coinciden con la fuente; los objetos de tabla
`_check_probability`, `_default_order_idx` y `_check_number_of_months` ya
viven en `Meta`. `_user_id_team_id_type_index` y `_create_date_team_id_idx`
no: quedan en `crm-table-objects-0397`.

Seguridad (`odoo19c: addons/crm/__manifest__.py`, clave `data`):
`security/crm_security.xml` y `security/ir.model.access.csv` (32 filas).

`crm.lead` hereda de `format.address.mixin`, que la fuente declara
`class FormatAddressMixin(models.AbstractModel)`
(`odoo19c: odoo/addons/base/models/res_partner.py:61`).

## Cambios

1. Los seis modelos derivan de `models.BaseModel`.
2. `FormatAddressMixin` declara `_abstract = True`: es un `AbstractModel` en
   la fuente, y `_check_model_parent_extension` rehúsa que un modelo con
   nombre extienda un padre nombrado no abstracto.
3. `addons/crm/security/`: el XML y el CSV, copia fiel, en `data` del
   manifiesto en el orden de la fuente, sin los registros cuyo destino no
   tiene puerto (el menú de `contacts`, las reglas de `crm.activity.report`
   y de `mail.activity.plan`; las filas de calendario, planes de actividad,
   el informe y los cuatro asistentes). Quedan 5 registros del XML y 18 filas
   del CSV; las omisiones se declaran en el manifiesto con su sucesor.
4. `CrmLead.action_unarchive` ≙ `odoo19c: addons/crm/models/crm_lead.py:1101-1110`:
   `activated = self.filtered(lambda rec: not rec.active)`, borra
   `lost_reason_id` con `write` y recalcula las probabilidades de cada
   reactivado. El puerto leía `not self.active`, verdadero sobre el recordset
   vacío que `toggle_active` le pasa (`odoo19c: odoo/orm/models.py:5788-5794`),
   y guardaba una fila inexistente.
5. `BaseModel._from_ids` (`src/orm/models.py`) marca `_state.adding = False`
   cuando todos los ids son reales: un `browse` de la fuente nombra filas
   existentes y su escritura es un UPDATE (`odoo19c: odoo/orm/models.py:5882`).
   Sin ello, `save()` sobre un registro iterado tomaba el camino de alta
   (precompute de `pre_save`). Un `NewId` o el recordset vacío conservan el
   `adding` de Django.
6. `test_basemodel_reach.py`: `crm` sale de `PENDING`.

## Consumidores ajustados (suite derivada)

- `tests/integration/crm/test_basemodel_contract_reach.py`: superusuario
  salvo en la prueba de ACL; el motivo de pérdida vacío es un recordset vacío.
- `tests/integration/sale/test_sale_crm.py`: el One2many `leads` es un
  recordset (`in` sin `.all()`).
- `tests/unit/orm/test_determine_inverse.py`: superusuario.
- `tests/unit/web/test_models_onchange.py`: los dos registros de la prueba
  de identidad salen de `new()`.

## Fuera de esta unidad, con su sucesor

- Los registros de modelos sin puerto — `crm-report-models-0397`.
- Los dos índices de tabla que faltan — `crm-table-objects-0397`.

## Pruebas

`tests/unit/crm/test_crm_basemodel.py`: los seis modelos son `BaseModel`;
grupos y reglas cargados; 18 filas de ACL; un usuario interno sin grupo de
ventas no lee una iniciativa; reactivar un recordset vacío no escribe; un
registro de `browse` guarda como UPDATE. Control de anulación: con el
`action_unarchive` anterior cae exactamente la prueba de reactivado; sin la
marca de `_from_ids` cae exactamente la de `browse`.
