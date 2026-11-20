# `Many2many(ondelete=…)`: la política de `column2` en la intermedia

Unidad `many2many-column2-ondelete-0122` (TASK-API-0122, ORM). Sucesor
declarado en `variant-combination-source-relation.md`.

## Contrato medido en la referencia

`odoo19c: odoo/orm/fields_relational.py:1253`: `ondelete: OnDelete | None =
'cascade'  # optional ondelete for the column2 fkey`, y
`update_db_foreign_keys` (`:1355-1367`): `column1` → tabla del modelo con
`'cascade'`; `column2` → tabla del comodelo con `self.ondelete`.

Censo por AST de `odoo19c` (`addons/**/models/*.py` y
`odoo/addons/**/models/*.py`): **19** `Many2many` declaran un `ondelete`
distinto de `cascade`, los 19 `restrict`: `crm.stage.team_ids`, las tres
`bom_product_template_attribute_value_ids` de `mrp`,
`account.tax.repartition.line.tag_ids`,
`account.reconcile.model.line.tax_ids`, `account.account.tag_ids`,
`account.move.line.tax_tag_ids`, `project.task.personal_stage_type_ids`,
`product_no_variant_attribute_value_ids` de compra y venta,
`product.product.product_template_attribute_value_ids` y
`product_template_variant_value_ids`,
`product.template.attribute.line.value_ids`, `calendar.event.alarm_ids`,
`sale.order.line.route_ids` (`sale_stock`), `ir.rule.groups` y dos de
`test_orm` (`b_restricted_b_ids`, `a_restricted_a_ids`).

## Estado del puerto

`Many2manyField` (`src/orm/fields_relational.py:929`) nombra tabla y
columnas, pero no acepta `ondelete`: las dos FK de la intermedia automática
son `CASCADE`. `foreign-keys-delete-contract.md` (tabla del punto 4) dejó
escrito «la tabla automática no admite `on_delete`»; el campo ya modifica la
intermedia generada (fija las columnas en `:1077`), así que el `on_delete`
de `column2` se puede fijar en el mismo punto.

## Medido antes de abrir

- **El `Collector` respeta `PROTECT` en una intermedia `auto_created`.**
  Sonda `EXPERIMENTAL` (fuera del árbol): con `on_delete=PROTECT` fijado en
  tiempo de ejecución sobre la FK de `column2` de
  `product_variant_combination`, borrar un PTAV usado levanta
  `ProtectedError`, y borrar la variante sigue cascadeando su fila
  (`column1`). No hace falta intermedia explícita.
- **Hoy `fields.Many2many(ondelete=…)` no llega a nada**: el despachador
  pasa la palabra a `ManyToManyField`, que la rechaza; ningún modelo del
  puerto la declara.
- **El control de la fuente no está portado**: `test_orm.model_a` y
  `test_orm.model_b` (`odoo19c: odoo/addons/test_orm/models/test_orm.py:
  1275-1290`) y sus pruebas `test_10_ondelete_many2many` y
  `test_11_ondelete_many2many` (`tests/test_fields.py:3350-3376`).
- **El `restrict` vive en el segundo extremo.** `rel_model_a_model_b_1` la
  declaran `A.a_restricted_b_ids` (sin `ondelete`) y `B.a_restricted_a_ids`
  (`ondelete='restrict'`, cuyo `column2` es la columna de `model_a`). En el
  puerto el segundo extremo es un espejo (`mirror_of`) que no crea tabla:
  su `ondelete` se aplica a la FK de `column1` del primero.

## Cambios

1. `Many2manyField(ondelete=…)`: `'cascade'` por defecto, como la fuente;
   `'restrict'` fija `on_delete=PROTECT` en la FK de `column2` de la
   intermedia automática, o en la de `column1` del dueño cuando el campo
   es un espejo. Otro valor se rehúsa nombrando el campo (el censo sólo
   tiene `restrict`). `deconstruct` lo conserva. El despachador
   `fields.Many2many` envía a `Many2manyField` cuando aparece `ondelete`.
2. Portar `test_orm.model_a` y `test_orm.model_b` con sus dos relaciones y
   las dos pruebas de la fuente. **Divergencia de mecanismo**: la fuente
   espera `psycopg2.IntegrityError` (la FK `ON DELETE RESTRICT`); aquí es
   `ProtectedError` antes del SQL, como el resto de `restrict` del puerto
   (`foreign-keys-delete-contract.md`, determinación 3).
3. Declarar `ondelete='restrict'` en los dos del censo que acaban de tomar
   la relación de la fuente: `ProductProduct.product_template_attribute_
   value_ids` y `ProductTemplateAttributeLine.value_ids`.
4. Los otros 14 del censo (crm, mrp, account, project, compra, venta,
   calendar, sale_stock, ir.rule) quedan para
   `many2many-ondelete-declarations-0122`: cada uno exige primero que su
   campo tenga la relación de la fuente.
