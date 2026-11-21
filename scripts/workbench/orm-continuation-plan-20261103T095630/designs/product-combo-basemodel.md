# product.combo y product.combo.item a BaseModel

Unidad `basemodel-adoption-0397`, tramo product. Referencia
`odoo19c: addons/product/models/product_combo.py` (79 líneas) y
`odoo19c: addons/product/models/product_combo_item.py` (33 líneas).

## Estado heredado medido

Los dos modelos son Django con `TimeStampedModel`. Las invariantes viven en
`clean()` y en `ProductCombo.check_has_items()`, que alguien tiene que llamar:
la prosa del módulo lo justifica con que Django persiste el padre antes que
los hijos. Con `BaseModel.create`, el One2many llega como comandos en la
misma escritura y la restricción corre después de escribirlos, igual que en
la fuente. La justificación ya no es cierta.

Dos frases de prosa heredada son falsas:

| Prosa | Medido | Veredicto |
|---|---|---|
| `ResCurrency._convert` no está portado | `src/addons/base/models/res_currency.py:536` | falso |
| `_get_main_company()` no existe | `ResCompany.get_main_company` (`src/addons/base/models/res_company.py:926`) | falso; el nombre diverge |

## Contrato a portar

`ProductCombo`:
- `ProductCombo._compute_combo_item_count` (`:33-43`)
- `ProductCombo._compute_currency_id` (`:45-51`), con respaldo a la compañía
  principal
- `ProductCombo._compute_base_price` (`:53-63`), con `_convert`
- `ProductCombo._check_combo_item_ids_not_empty` (`:65-68`)
- `ProductCombo._check_combo_item_ids_no_duplicates` (`:70-74`)
- `ProductCombo._check_company_id` (`:76-80`)
- `sequence` lleva `copy=False` y `combo_item_ids` lleva `copy=True`.

`ProductComboItem`:
- `company_id` related a `combo_id.company_id`, almacenado y precalculado
- `currency_id` y `lst_price` related al producto
- `ProductComboItem._check_product_id_no_combo` (`:30-33`)
- el `domain` del producto

Las citas se pasan a la línea `def` antes de commitear.

## Implementación

- `addons/product/models/product_combo.py`: `ProductCombo` deriva de
  `(models.BaseModel, TimeStampedModel)`. Campos de la fuente
  (`combo_item_count`, `currency_id`, `base_price` calculados sin columna;
  `sequence` con `copy=False`) y métodos
  `ProductCombo._compute_combo_item_count`
  (`odoo19c: addons/product/models/product_combo.py:33-42`),
  `ProductCombo._compute_currency_id` (`:45-50`),
  `ProductCombo._compute_base_price` (`:53-62`),
  `ProductCombo._check_combo_item_ids_not_empty` (`:65-67`),
  `ProductCombo._check_combo_item_ids_no_duplicates` (`:70-73`) y
  `ProductCombo._check_company_id` (`:76-79`). La fecha de la conversión es
  `record_transaction_now`, el `cr.now()` de este árbol. Se retiran
  `ProductCombo.clean`, `ProductCombo.check_has_items`, las propiedades y el
  M2M `product_tmpls`.
- `addons/product/models/product_combo_item.py`: `ProductComboItem` deriva
  de `BaseModel`; `company_id` `related` almacenado y precalculado,
  `currency_id` y `lst_price` `related` al producto, `product_id` con
  `check_company` y `domain`, y `ProductComboItem._check_product_id_no_combo`
  (`odoo19c: addons/product/models/product_combo_item.py:31-33`). Se retiran
  `ProductComboItem.save`, `ProductComboItem.clean` y las propiedades.
- `ProductTemplate.combo_ids` se declara en la plantilla, como en la fuente
  (`odoo19c: addons/product/models/product_template.py:66-70`), con
  `ProductTemplate._check_combo_ids_not_empty` (`:490-493`) y
  `ProductTemplate._check_sale_combo_ids` (`:496-507`); se retira
  `ProductTemplate.check_combo_choices`.
- **Migración 0056** `addons/product/migrations/0056_combo_basemodel.py`:
  renombra la tabla `product_combo_product_tmpls` a
  `product_combo_product_template_rel` y sus columnas a las de la fuente,
  sin perder filas.
- `extra_price` y `base_price` son `Monetary`, no `Float`: suman o comparan
  `lst_price`, que aquí ya es `Monetary`.

## Lo que destapó el porte en el ORM

1. **`BaseModel.mapped` rehusaba la rama relacional** con
   `NotImplementedError` citando TASK-API-0401. La rama de varios registros
   ya existía (`BaseModel._read_relational_multi`, llamada desde
   `_read_field`): `mapped` ahora devuelve `records._read_field(field)`, el
   `getter(records)` de la fuente, y el comodelo vacío cuando no hay
   registros (el nulo de lectura del stack es `None`). TASK-API-0401 conserva
   su alcance: el acceso llano `rs.campo` sobre N registros.
2. **Un `related` con `precompute=True` no se precalculaba**:
   `_run_precompute_field` (`src/orm/models.py`) llamaba
   `getattr(instance, field.compute)`, y en un `related` `compute` es el
   invocable `_compute_related`. Ahora despacha con `determine`, como
   `_invoke_compute_method`.
3. **`_check_company` no veía la compañía de `product.product`**: la variante
   la alcanza por `_inherits`, y `_first_field_name` sólo miraba campos
   propios. Ahora acepta también un nombre delegado (el
   `'company_id' in self` de la fuente cuenta los campos `inherited`), y
   `_field_attname` lo nombra tal cual en el dominio. Lo consumen
   `CheckCompanyMixin._check_company_domain`
   (`odoo19c: odoo/orm/models.py:3997-4007`) y
   `check_company_domain_parent_of` (`odoo19c: odoo/orm/models.py:169-185`),
   que construyen el dominio con ese nombre; su prueba es
   `test_an_option_of_another_company_is_refused`. Se retira la propiedad
   `ProductProduct.company_id`, que ocultaba la delegación igual que
   `list_price`.

## Premisas de prueba que cambian

- `tests/unit/orm/test_reverse_many2many_assignment.py` medía la asignación
  del lado inverso con `combo_ids`, que ya no es inverso: ahora la mide con
  `product_tag_ids`, el inverso de `ProductTag.product_template_ids`.
- `tests/unit/product/test_product_combo_source_names.py` pierde el caso de
  `combo.clean()`; la validación de compañía la mide el archivo nuevo.
- `tests/unit/product/test_product_models.py` pierde los tres casos de
  `check_combo_choices`; los miden las restricciones del archivo nuevo.
- `tests/unit/product/test_template_crud.py` crea la plantilla combo con su
  elección en el mismo `create`, porque la restricción ya corre al crear.

## Pruebas y anulación

`tests/unit/product/test_product_combo_basemodel.py` (12 casos). Anulación:
las cinco restricciones, el conteo, el mínimo, la moneda, `check_company`,
`copy=False`, y en el ORM la compañía delegada, el despacho del precalculado
y el comodelo vacío de `mapped` tiran cada uno sus casos.

## Fuera de este tramo

- `_onchange_type` (`odoo19c: addons/product/models/product_template.py:460-471`)
  es un `onchange`; aquí sigue como `check_combo_has_no_attributes`. Su porte
  va con el resto de los onchange de la plantilla.
