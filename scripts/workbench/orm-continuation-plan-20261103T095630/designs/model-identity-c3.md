# C3 — las columnas de modelo guardan la identidad contractual

Fecha: 2026-11-23T08:35:25. TASK-API-0397. Corte C3 de `model-identity-contract.md`.
Referencia: `'model': model._name`
(`odoo19c: odoo/addons/base/models/ir_model.py:428`); `ir.rule` resuelve por
`model_id.model` (`odoo19c: odoo/addons/base/models/ir_rule.py:24`); el
reflejo de campos e herencia corre en `init_models`
(`odoo19c: odoo/orm/registry.py:754-758`).

Prueba del corte: `tests/integration/base/test_model_identity_columns.py`
(9 casos), más `tests/unit/orm/test_model_identity.py` de C1.

## Qué cambia

Toda escritura de las columnas `ir_model.model`, `ir_model_fields.model` y
`relation`, `ir_model_data.model`, `ir_rule.model_name`,
`ir_act_server.model_name`, `ir_act_report_xml.model` y
`base_automation.model_name`/`trg_field_ref_model_name` guarda
`registry.identity_of(cls)`; todo cotejo normaliza la entrada con
`registry.identity_for_key`; toda resolución de columna a clase usa
`registry.model_by_key`, que acepta las dos formas. Las siembras corren sobre
modelos históricos sin `_name`, así que llevan su etiqueta por
`identity_for_key`, que resuelve contra el registro vigente.

## Símbolos

| Archivo | Símbolos |
|---|---|
| `src/addons/base/models/ir_model.py` | `_model_class`, `django_model`, `_inherited_models`, `_get_id`, `_reflect_models`, `_reflect_field_params`, `_reflect_inherits`, `_reflect_selections`, `_reflect_constraint`, `_reflect_relation`, `modules`, `_get_ids`, `_get_fields_cached`, `_model_label`, `_make_access_error`, `_update_xmlids`, `_module_data_uninstall`, `delete`, `ref`, `toggle_noupdate` |
| `src/addons/base/models/ir_rule.py` | `_check_domain`, `_get_rules`, `_compute_domain`, `_parent_rule_domains`, `_get_failing`, `_failing_rules`, `_make_access_error`, `for_current_company`, `model_name` (sólo `help_text`) |
| `src/addons/base/models/ir_actions.py` | `_crud_model`, `_active_record`, `_get_relation_chain`, `_traverse_path`, `_get_eval_context` |
| `src/addons/base/models/ir_actions_report.py` | `valid_reports_for` |
| `src/addons/base/models/ir_cron.py` | `toggle` |
| `src/addons/base/models/ir_fields.py` | `_xmlid_to_record_id` |
| `src/addons/base/models/ir_module.py` | `_compute_xml_id` |
| `src/addons/base/models/ir_ui_view.py` | `_fetch_template_views` |
| `src/addons/base/models/properties_base_definition.py` | `_get_definition_id_for_property_field` |
| `src/addons/base/models/properties_base_definition_mixin.py` | `properties_model_label` |
| `addons/base_automation/models/base_automation.py` | `_get_eval_context`, `_execute_webhook`, `_get_actions`, `_cron_process_time_based_actions` |
| `addons/base_automation/models/signals.py` | `_model_name` |
| `addons/uom/models/uom_uom.py` | `filter_protected_uoms` |
| `addons/web/models/ir_model.py` | `_is_valid_for_model_selector`, `_display_name_for` |
| `src/orm/models.py` | `_check_access`, `_get_external_ids`, `get_metadata`, `_model_description`, `_load_records`, `_search`, `__ensure_xml_id` |
| `src/orm/registry.py` | `_reflect_all` |
| `src/orm/fields_properties.py` | `_model_of` |
| `src/orm/migration_operations.py` | `RewriteModelIdentities`, `__init__`, `_rewrite`, `_reject_collisions` |
| migraciones | `0128_rewrite_model_identities` (`base`), `0009_rewrite_model_identities` (`base_automation`) |

Siembras (fuera del gate, mismo criterio): `src/addons/base/data/cron.py`,
`res_groups_data.py`, `res_country_data.py`, `src/modules/db.py`,
`src/addons/base/security/ir_model_access.py`, `base_security.py`, y los
`data/` de `account`, `account_check_printing`, `account_fleet`,
`account_test`, `analytic`, `base_install_request`, `hr` y `l10n_mx`.

## Lo que destapó la implementación

1. **El reflejo de campos y de herencia nunca corría en `init_models`.**
   `Registry._reflect_all` llamaba `_reflect_fields` y `_reflect_inherits`
   sobre `ir.model`, que no los tiene: son de `ir.model.fields` e
   `ir.model.inherit`, como en la fuente. El fallo quedaba oculto porque el
   filtro buscaba `m._name` en una columna que guardaba la etiqueta y no
   devolvía filas. Con C3 las filas casan y el error apareció
   (`AttributeError` en `post_migrate`); se corrige pidiendo cada modelo al
   registro por su `_name`.
2. **`IrModuleCategory`.** `create_categories` comparaba la fila guardada
   con la etiqueta histórica; con la identidad nueva y sin migrar, la carga
   rehusaba (`Identidad de categoría incompatible`). Es la prueba de que
   escritores y migración tienen que ir juntos.
3. **`IrRule._check_model_name`** cotejaba `model_name == self._name`, que
   con la etiqueta no casaba nunca; ahora la guarda contra reglas sobre
   `ir.rule` puede disparar (lector latente de C4).

## Migración

`RewriteModelIdentities(table, column, unique_with)` en
`src/orm/migration_operations.py`: reescribe cada valor que
`identity_for_key` cambia, deja intactos los que ya son identidad o no
nombran un modelo vigente, y rehúsa —listando los choques— si la reescritura
duplicaría una clave única (`ir_model.model`, `(model, name)` de
`ir_model_fields`) en vez de fundir filas con referencias. Aplicada sobre la
base de pruebas: 0 choques, 0 etiquetas restantes en las ocho columnas.

## Fuera de C3

`ir_default.model`, `ir_filters.model_id`, `ir_attachment.res_model`,
`mail_message.model` y el `JOIN` de `base_partner_merge` entre
`ir_model_fields.model` e `ir_default.model` son el vocabulario de otras
tablas (cubo `X-vocab` de `outputs/model-identity-sites.tsv`). Sucesor:
`model-identity-vocab-columns-0397`.
