# product-pricelist-cluster-0397 — `product.pricelist` y `product.pricelist.item`

Unidades hijas de `basemodel-adoption-0397` (grupo `product`). Medición
hecha con un subagente de lectura (2026-11-21) y comprobada en sus puntos de
validación de prosa con `grep` en el árbol.

## Referencia y estado

- `odoo19c: addons/product/models/product_pricelist.py` (414 líneas): el
  puerto (125) declara cabecera y campos sin `required`/`translate`/
  valores por defecto; faltan `_default_currency_id`, los dominios de
  `item_ids`, `write`, `copy_data`, toda la familia de selección y precio
  (`_get_products_price` … `_compute_price_rule_multi`, `:90-286`), las
  tarifas por país y por cliente (`:288-385`), `get_import_templates`,
  `_unlink_except_used_as_rule_base` y `action_open_pricelist_report`.
- `odoo19c: addons/product/models/product_pricelist_item.py` (684 líneas,
  33 `def`): el puerto (461, 9 `def`) tiene los campos con cuatro
  `Monetary` donde la fuente declara `Float`, `price_markup` sin
  cómputo/inverso, y equivalentes con otro nombre y otra forma de
  `_is_applicable_for` (`matches`), `_compute_price` (`compute`) y
  `_compute_base_price` (`base_price_for`, que levanta
  `NotImplementedError` para `base='pricelist'`); faltan `create`,
  `write`, cinco restricciones como `@api.constrains`, los nueve
  `onchange`, las etiquetas y `_compute_price_before_discount`.

## Prosa heredada, validada

| Afirmación | Medido | Veredicto |
|---|---|---|
| la familia `_get_product_price` «se porta como `matches` y `best_rule_for`» | `best_rule_for` no está definido en el árbol (sólo citado en un docstring y en un test) | **falso** |
| la conversión de moneda no se porta porque no hay conversor con fecha y compañía | `ResCurrency._convert` existe (`src/addons/base/models/res_currency.py`) | **falso** |

## Consumidores

`sale` (dominio, `pricelist_id`, `_compute_has_active_pricelist`, la
extensión del ítem con `COMPUTE_PERCENTAGE`) y las pruebas de
`tests/unit/product/test_product_pricelist_*`. El precio de venta hoy es
`lst_price` (`addons/sale/services.py`, `sale_order_line.current_price`):
ninguna tarifa se consulta. En `product`, la fuente llama a la tarifa desde
`_get_contextual_price`/`_get_contextual_discount` y `_price_compute`, que
el puerto no tiene.

## Etapas, en orden de dependencia

1. `BaseModel` y paridad de campos de los dos modelos (cabeceras,
   valores por defecto, `Float`, `item_ids` con dominio, cómputos de
   empresa/moneda/markup/obligatoriedad, `_compute_display_name`).
2. Integridad: `create`/`write` del ítem, las cinco restricciones, `write`,
   `copy_data` y la guarda de borrado de la tarifa.
3. Precio de una regla: `_is_applicable_for`, `_compute_base_price` (con
   `_price_compute` en plantilla y variante, y `_convert`),
   `_compute_price`; sustituye `matches`/`compute`/`base_price_for` y
   repunta pruebas y la extensión de `sale`.
4. Selección y recursión: `_get_applicable_rules(_domain)`,
   `_compute_price_rule`, los cuatro envoltorios, `_price_get`,
   `_compute_price_rule_multi`, la rama `base='pricelist'`,
   `_compute_price_before_discount` y los `_get_contextual_*` de producto.
5. Etiquetas, `onchange`, tarifas por país y cliente (con
   `property_product_pricelist` de `res.partner`), importación y acción.

## Etapa 1 — anexo de implementación (2026-11-21)

`product.pricelist` (`odoo19c: addons/product/models/product_pricelist.py`):

- `ProductPricelist` pasa a `models.BaseModel` con `MailThread` y
  `MailActivityMixin`, como la fuente (`:9-11`).
- `_default_currency_id` (`:16`) y `default=lambda self: self.env.company`
  (`:43-47`) como callables de módulo `_default_currency_id` y
  `_default_company_id`.
- `_base_domain_item_ids` (`:19`) y `_domain_item_ids` (`:25`).
- `name` con `required=True` (`:28`; `translate` es TASK-GEN-0060), `currency_id` con su `default`,
  `required=True` y `tracking=1` (`:36-41`), `company_id` con `tracking=5` (`:43`).
- `item_ids` (`:58-64`) se declara como `One2many` con el dominio en lambda y
  `copy=True`; la FK `pricelist_id` del ítem pasa a `related_name='+'`.
- `_compute_display_name` (`:67`), `write` (`:72`, comprueba la empresa
  de las reglas al cambiar la empresa) y `copy_data` (`:82`).

`product.pricelist.item` (`odoo19c: addons/product/models/
product_pricelist_item.py`):

- `ProductPricelistItem` pasa a `models.BaseModel` con
  `_check_company_auto = True` (`:12`); `check_company=True` en
  `product_tmpl_id`, `product_id` y `base_pricelist_id` (`:80`, `:85`,
  `:104`). Esto cierra la sucesora `pricelist-item-check-company-0397`.
- `_default_pricelist_id` (`:14-17`) como callable de módulo.
- `is_pricelist_required` con `_compute_is_pricelist_required` (`:28`,
  `:167-168`).
- `company_id` y `currency_id` almacenados con `_compute_company_id` y
  `_compute_currency_id` (`:30-31`, `:170-182`); se retira el `save` que
  los fijaba a mano.
- `display_applied_on` (`:61-68`), `product_uom_name` y
  `product_variant_count` como `related` (`:87-88`).
- `fixed_price`, `price_surcharge`, `price_min_margin` y `price_max_margin`
  pasan de `Monetary` a `Float`, como la fuente (`:117-153`).
- `price_markup` almacenado con `_compute_price_markup` e
  `_inverse_price_markup` (`:136-142`, `:265-271`).
- `name` con `_compute_name` (`:155-158`, `:184-196`).

Queda para etapas posteriores, sin cambio de forma en esta: `clean` (lo
sustituyen las cinco `@api.constrains` de la etapa 2), `matches`/`compute`/
`base_price_for` (etapa 3) y las etiquetas `price`/`rule_tip` con
`_compute_price_label`/`_compute_rule_tip` (etapa 5).

Migraciones: `0059_pricelist_basemodel` (rellena la moneda nula antes de
declararla `NOT NULL`) y `0060_pricelist_item_basemodel`.

### Dos defectos del ORM destapados por la etapa 1

- `orm.models._readable_ids` (la rama de `copy_data` para `Many2many`,
  ≙ `odoo19c: odoo/orm/models.py:5459`,
  `record[name]._filtered_access('read').ids`) distinguía el recordset por
  `hasattr(value, '_filtered_access')`. El gestor relacionado de Django
  también expone ese método (lo hereda de `AccessQuerySet`) y devuelve un
  `QuerySet` sin `ids`, así que copiar una tarifa con `country_group_ids`
  (comodelo Django) fallaba. Se discrimina por `_ids`, como ya hace
  `_x2many_records`.
- `CheckCompanyMixin.save` verificaba la empresa justo tras el `INSERT`.
  Dentro de `BaseModel.create` la fila aún no tiene sus calculados
  almacenados (aquí, el `company_id` del ítem), y la fuente verifica una sola
  vez al final de `create` (`odoo19c: odoo/orm/models.py:4744`). El `save`
  omite la verificación mientras `ORM_CREATE_INSERTING` está activo; `create`
  la hace al final, como ya hacía.

### La extensión de `sale` pasa a recordset

`odoo19c: addons/sale/models/product_pricelist_item.py:7-15`:
`_is_discount_feature_enabled` vuelve a ser `@api.model` (era
`classmethod`) y `_show_discount` recupera sus dos guardas
(`if not self: return False` y `self.ensure_one()`), que con el ítem como
`BaseModel` vuelven a poder dispararse.

### Símbolos tocados en la etapa 1, con su prueba

Además de los ya nombrados, cambian de forma: `_default_company_id` (el
`default=lambda self: self.env.company` de `odoo19c:
addons/product/models/product_pricelist.py:43-47`); los campos `Float`
`fixed_price`, `percent_price`, `price_discount`, `price_round`,
`price_surcharge`, `price_min_margin`, `price_max_margin` y la selección
`compute_price` (`odoo19c: addons/product/models/product_pricelist_item.py:108-153`),
con la cabecera `string`/`help`/`required` de la fuente; `product_uom_name`
(`:87`); y `apply_sale_pricelist_item_extensions`, que cuelga
`_is_discount_feature_enabled` sin `classmethod`
(`odoo19c: addons/sale/models/product_pricelist_item.py:7-15`).
`_readable_ids` sigue a `odoo19c: odoo/orm/models.py:5459`. Las migraciones
`0059_pricelist_basemodel` y `0060_pricelist_item_basemodel` llevan el
esquema a esos campos; la segunda termina con `ComputeStoredFields` para
`company_id`, `currency_id` y `price_markup` (`odoo19c:
odoo/orm/models.py:3220-3238`).

Pruebas:

- `tests/unit/product/test_product_pricelist_basemodel.py` — valores por
  defecto de la tarifa, nombre para mostrar, copia con reglas y grupos de
  países (`_readable_ids`), verificación de empresa en `write`, cabecera del
  ítem, empresa y moneda calculadas, `_default_pricelist_id`, margen e
  inverso, `_compute_name` y los `Float`.
- `tests/unit/product/test_product_security.py` — empresa y moneda del ítem
  con y sin tarifa (la verificación de empresa al final de `create`).
- `tests/unit/product/test_product_pricelist_item_source_names.py` —
  `item_ids` como `One2many`.
- `tests/unit/orm/test_new_computed_columns_are_computed.py` — el
  `ComputeStoredFields` de `0060_pricelist_item_basemodel`.
- `tests/unit/orm/test_basemodel_reach.py` — `product` sale de las apps
  pendientes de `BaseModel`.
- `tests/integration/sale/test_sale_order_nonstored_fields.py` — la tarifa
  global del pedido con su moneda obligatoria.

`_show_discount` y `_is_discount_feature_enabled` no tienen consumidor ni
prueba en el árbol (medido con `grep -rn` en `addons` y `tests`); su prueba
es `tests/unit/sale/test_sale_pricelist_item_discount.py`, añadida en esta
etapa.

## Etapa 2 — integridad

`odoo19c: addons/product/models/product_pricelist_item.py`:

- `create` (`:479-508`): deduce `product_tmpl_id` de `product_id`, infiere
  `applied_on` cuando no viene y limpia los campos de alcance que no le
  corresponden, para que las búsquedas posteriores sean coherentes.
- `write` (`:510-522`): la misma limpieza cuando se escribe `applied_on`.
- Las cinco restricciones como `@api.constrains`, verbatim:
  `_check_base_pricelist_id` (`:316-319`), `_check_pricelist_recursion`
  (`:321-352`, búsqueda en profundidad con su función interna `dfs_path`
  (`odoo19c: addons/product/models/product_pricelist_item.py:323-343`) y
  `_read_group` sobre `base_pricelist_id`), `_check_date_range` (`:354-364`, fin estrictamente
  posterior al inicio), `_check_margin` (`:366-369`) y
  `_check_product_consistency` (`:371-381`).
- Se retira `clean`: sus tres comprobaciones son las de
  `_check_product_consistency`, `_check_base_pricelist_id` y
  `_check_date_range`, que en la fuente corren en cada escritura del ORM y
  no sólo en `full_clean` (medido: ningún consumidor llama a `full_clean`
  ni a `clean` de la regla).

`odoo19c: addons/product/models/product_pricelist.py`:

- `_unlink_except_used_as_rule_base` (`:393-405`) con
  `@api.ondelete(at_uninstall=False)`: una tarifa que otra usa como base
  no se borra.

Prueba: `tests/unit/product/test_product_pricelist_integrity.py` — cada
restricción con su caso que la viola y su caso válido, la recursión directa
e indirecta, la deducción de plantilla e inferencia de alcance en `create`,
la limpieza en `create` y `write`, y la guarda de borrado.

### Dos ajustes destapados por la guarda de borrado

- `base_pricelist_id` (`odoo19c: addons/product/models/product_pricelist_item.py:104`)
  no declara `ondelete`, así que toma el valor por defecto de un `Many2one`
  no obligatorio, `'set null'` (`odoo19c: odoo/orm/fields_relational.py:282`).
  El puerto lo tenía en `PROTECT`, y eso impedía borrar juntas la tarifa base y
  la derivada aunque la guarda lo admite. Migración
  `0061_pricelist_item_base_set_null`.
- `_run_ondelete_on_delete` llamaba a cada método `@api.ondelete` registro a
  registro. La fuente lo llama una vez con el recordset entero
  (`odoo19c: odoo/orm/models.py:4205-4208`, `func(self)`), y una guarda que
  mira el conjunto —como `_unlink_except_used_as_rule_base`, que excluye las
  reglas de las tarifas que se borran a la vez— sólo es correcta así. Para un
  `BaseModel` se pasa el recordset; un modelo de Django sigue recibiendo la
  instancia.

Prueba: `tests/unit/product/test_product_pricelist_integrity.py`
(`test_deleting_both_pricelists_together_is_allowed` y
`test_a_pricelist_used_as_a_base_cannot_be_deleted`).
