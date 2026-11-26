# Adopción de BaseModel: properties.base.definition (basemodel-adoption-0397)

## Referencia

- `odoo19c: odoo/addons/base/models/properties_base_definition.py:6-67` —
  `class PropertiesBaseDefinition(models.Model)`; `properties_definition =
  fields.PropertiesDefinition(...)` (`:17`); `write` rehúsa cambiar
  `properties_field_id` con `AccessError` (`:43-46`); `_compute_display_name`
  recorre `self` (`:24-34`).
- ACL: `odoo19c: odoo/addons/base/security/ir.model.access.csv:147`
  (`group_system`, 1,1,1,1).
- Regla: `odoo19c: odoo/addons/base/security/base_security.xml:256-261`
  (`properties.base.definition: system all access`, `[(1, '=', 1)]`,
  `group_system`).

## Hallazgo: el derivador de la ACL descartaba las filas calificadas

`probes/derive_base_acl.py` busca cada fila del CSV por `model_` + `_name`,
sin módulo. Las tres últimas filas del CSV califican el identificador
(`base.model_res_device`, `base.model_res_device_log`,
`base.model_properties_base_definition`, `:145-147`) y caían en «sin modelo»
aunque los tres modelos existen con `_name`. Corregido quitando el prefijo
`base.`: el derivador pasa de 98 a 101 filas, y `_ACCESS` recibe esas tres.
No se registra en `agent_store` porque esta VM no escribe en esa base.

## Cambio

1. `PropertiesBaseDefinition(models.BaseModel, TimeStampedModel)`.
2. `properties_definition = fields.PropertiesDefinition(...)` como la fuente
   (la columna sigue siendo `jsonb`).
3. `write` como la fuente: `properties_field_id` (o `properties_field`) en
   `vals` levanta `AccessError`; si no, `super().write(vals)`. El guardián de
   `save()` se conserva para el camino de Django.
4. `_compute_display_name` recorre el recordset.
5. La regla entra en `_RULES`; las tres filas de ACL en `_ACCESS`; una
   migración de datos las siembra en bases ya migradas.

## Pruebas

- `tests/unit/base/test_properties_base_definition_basemodel.py`: la base;
  `write` del campo apuntado levanta `AccessError`; la regla sembrada; la fila
  de ACL de `group_system`.

## Símbolos del cambio, con su cita y su prueba

| Símbolo | Referencia | Prueba |
|---|---|---|
| `PropertiesBaseDefinition` (base, `properties_definition`) | `odoo19c: odoo/addons/base/models/properties_base_definition.py:6-17` | `tests/unit/base/test_properties_base_definition_basemodel.py` |
| `PropertiesBaseDefinition.write` | `odoo19c: odoo/addons/base/models/properties_base_definition.py:43-46` | `tests/unit/base/test_properties_base_definition_basemodel.py` |
| `PropertiesBaseDefinition._compute_display_name` | `odoo19c: odoo/addons/base/models/properties_base_definition.py:24-34` | `tests/unit/base/test_properties_base_definition.py` |
| `0133_seed_properties_and_device_security` | `odoo19c: odoo/addons/base/models/properties_base_definition.py:6-10` | `tests/unit/base/test_properties_base_definition_basemodel.py` |

## Medido

- 4 casos nuevos en rojo antes del cambio; 37 verdes con el archivo existente
  (`tests/unit/base/test_properties_base_definition.py`, cuyo caso de
  escritura pasa a `sudo()` porque ahora aplica la ACL).
- Anulación (base revertida): caen exactamente los 2 casos que dependen de
  `BaseModel` (la base y la escritura); los de la derivación y la regla
  sobreviven. Restaurada con `cmp`.
- Subconjunto derivado (`PropertiesBaseDefinition|properties.base.definition|properties_definition|_get_definition_id_for_property_field|ResDevice|res.device|res_device|_ACCESS|IrModelAccess|base_security|seed_base_acl`,
  78 archivos, `-n 4`): 953 passed y 13 failed, todos en
  `tests/integration/base/test_ir_model_access_check.py` y
  `test_ir_model_access_groups.py`. Su ancla era `res.device.log` *porque no
  tenía fila de ACL*, y esa ausencia era el defecto del derivador; los dos
  archivos lo preveían («si algún día entra en la ACL de base … hay que mover
  el ancla»). Pasa a `ir.autovacuum`, el único modelo de `base` con `_name`
  que el sembrador no cubre (medido), `AbstractModel` sin fila en la fuente.
  Con el ancla movida: 38 passed.
