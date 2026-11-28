# `country_ids` de `ir.module.module`

Sucesora de `designs/ir-module-versions.md`. TASK-API-0397.

## Contrato medido en la referencia

- `odoo19c: odoo/addons/base/models/ir_module.py:297`
  `country_ids = fields.Many2many('res.country', 'module_country', 'module_id', 'country_id')`.
- Su escritor es `_update_countries` (`:842-850`), que escribe la tabla
  `module_country` con SQL crudo sobre las columnas `module_id` y
  `country_id`.
- Su lector es `res.company._compute_uninstalled_l10n_module_ids`
  (`odoo19c: odoo/addons/base/models/res_company.py:207-241`), que une
  `module_country mc` por esas columnas.

## Lo que esta unidad hace

Declara el campo con la firma de la fuente; el `Many2many` del puerto acepta
`(comodel, relation, column1, column2)` (`orm/fields_relational.py:929-1010`),
así que la tabla y sus dos columnas salen con los nombres de la fuente. La
migración crea la tabla (`AddField`). El campo no tiene `related_name` propio
en la fuente: el reverso es `'+'`.

Lo que no cierra: `_update_countries` y el cómputo de `res.company` son las
unidades que lo consumen; quedan para el grupo de `_update_*` y para el
consumidor de `res.company`.

## Pruebas (RED)

`tests/unit/base/test_ir_module_country_ids.py`: la tabla `module_country`
con columnas `module_id` y `country_id`, y la lectura de `country_ids` desde
un módulo.
