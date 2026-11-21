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

## Etapa 3 — precio de una regla

`odoo19c: addons/product/models/product_pricelist_item.py`:

- `_is_applicable_for` (`:526-568`) sustituye a `matches`: cantidad mínima,
  categoría por `parent_path`, plantilla o variante, y la variante aceptable
  sobre una plantilla de una sola variante.
- `_compute_price` (`:570-626`) sustituye a `compute`: `self` es como mucho
  un registro (vacío = precio base), conversión de unidad con
  `product_uom._compute_price` y moneda de destino
  `currency or self.currency_id or self.env.company.currency_id`.
- `_compute_base_price` (`:628-659`) sustituye a `base_price_for`: base
  `pricelist` por `base_pricelist_id._get_product_price` (etapa 4), coste o
  precio de lista por `product._price_compute`, y conversión con
  `src_currency._convert(price, currency, self.env.company, date,
  round=False)`.

`odoo19c: addons/product/models/product_template.py` y `product_product.py`:

- `_get_attributes_extra_price` (`:732-735`, `:1096-1099`) y
  `_price_compute` (`:737-768`, `:1101-1130`) en plantilla y variante.

Consumidores que se repuntan: `tests/unit/product/test_product_template_uom_id.py`,
`tests/unit/product/test_product_template_categ_id.py`,
`tests/unit/product/test_product_pricelist_item_source_names.py`.

### Tres ajustes de la etapa 3

- Las etiquetas de `APPLIED_ON_CHOICES`, `BASE_CHOICES` y
  `COMPUTE_PRICE_CHOICES` pasan a las de la fuente
  (`odoo19c: addons/product/models/product_pricelist_item.py:51-58`,
  `:90-96`, `:106-114`), con el orden de `applied_on` de la fuente. La prosa
  heredada decía «verbatim» sobre etiquetas traducidas: era falso. Migración
  `0062_pricelist_item_choice_labels`.
- `with_company` (`odoo19c: odoo/orm/models.py:5991`) hacía `int(company)`;
  `res.company` sigue siendo un modelo de Django y su instancia no tiene
  `__int__`, así que se toma su `pk`. `_price_compute` lo llama con
  `self.env.company`.
- `_price_compute` lleva el precio a `float`: el `Monetary` de este ORM es
  un `DecimalField`, y la fuente calcula en `float`. `_compute_base_price`
  hace lo mismo con el `Decimal` que devuelve `_convert`.

Pruebas: `tests/unit/product/test_product_pricelist_rule_price.py`, con
`tests/unit/product/test_product_template_uom_id.py`,
`tests/unit/product/test_product_template_categ_id.py` y
`tests/unit/product/test_product_pricelist_item_source_names.py`
repuntadas a `_is_applicable_for` y `_compute_price`.

## Etapa 4 — selección de reglas y recursión

`odoo19c: addons/product/models/product_pricelist.py`:

- Los cuatro envoltorios `_get_products_price` (`:90`), `_get_product_price`
  (`:112`), `_get_product_price_rule` (`:131`) y `_get_product_rule`
  (`:150`) sobre `_compute_price_rule` (`:169-237`): moneda de destino,
  fecha por defecto `fields.Datetime.now()`, cantidad en la unidad del
  producto con `_compute_quantity(..., raise_if_failure=False)`, la primera
  regla aplicable en el orden del modelo y el precio con
  `_compute_price`.
- `_get_applicable_rules` (`:239`) y `_get_applicable_rules_domain`
  (`:248-265`), con `parent_of` sobre la categoría.
- `_price_get` (`:268`) y `_compute_price_rule_multi` (`:274-287`).

`odoo19c: addons/product/models/product_pricelist_item.py`:

- `_compute_price_before_discount` (`:661-684`) y, por la rama
  `base='pricelist'` de `_compute_base_price`, la recursión entre tarifas.

`odoo19c: addons/product/models/product_template.py` y `product_product.py`:

- `_get_contextual_price` (`:1537-1543`, `:1170-1173`),
  `_get_contextual_pricelist` (`:1545-1550`), `get_contextual_price`
  (`:1167-1168`) y `_get_contextual_discount` (`:1175-1193`).

Prueba: `tests/unit/product/test_product_pricelist_selection.py`.

### Un defecto del ORM destapado por la etapa 4

`_forward_get` (la lectura de un `Many2one`) construía el corecord en el
entorno ambiental (`env()`), no en el del registro que lee. La fuente lo
construye en `record.env` (`Many2one.convert_to_record`,
`odoo19c: odoo/orm/fields_relational.py:354-358`, y
`convert_to_record_multi`, `:360-364`), así que el valor hereda el contexto,
el usuario y el `su`. Sin eso, `_get_contextual_price` de la variante
(`odoo19c: addons/product/models/product_product.py:1170`) llegaba a la
plantilla sin la clave `pricelist` del contexto y devolvía el precio de
lista. El corecord vacío y el de varios registros también se construyen
ahora en el entorno del registro.

Pruebas: `tests/unit/orm/test_many2one_record_env.py` (contexto, `su` y
valor vacío) y `tests/unit/product/test_product_pricelist_selection.py`
(`test_the_contextual_price_and_discount_read_the_pricelist`).

## Etapa 5 — etiquetas, `onchange`, tarifa por país, importación y acción

Se parte en dos, por una dependencia medida:

**5a, ahora.** `odoo19c: addons/product/models/product_pricelist_item.py`:
`price` y `rule_tip` (`:159-163`) con `_compute_price_label` (`:216`),
`_get_price_label_base_str` (`:198`), `_compute_rule_tip` (`:277`),
`_get_integer` (`:306`) y `_get_displayed_discount` (`:309`); los nueve
`onchange` (`:383-477`). `odoo19c: addons/product/models/product_pricelist.py`:
`_get_country_pricelist_multi` (`:288-330`),
`_get_partner_pricelist_multi_search_domain_hook` (`:377`),
`_get_partner_pricelist_multi_filter_hook` (`:383`),
`get_import_templates` (`:387`) y `action_open_pricelist_report`
(`:408`).

**5b, sucesora.** `_get_partner_pricelist_multi` (`:334-375`) y la extensión
de `res.partner` de `product` (`odoo19c: addons/product/models/
res_partner.py`: `property_product_pricelist`,
`specific_property_product_pricelist` y su cómputo/inverso). Recorre
`res.partner` como recordset (`browse`, `grouped('country_id')`), y
`res.partner` sigue siendo un modelo de Django: depende de la adopción de
`BaseModel` en la app `base`. Sucesora: `product-partner-pricelist-0397`.

Prueba: `tests/unit/product/test_product_pricelist_labels.py`.

### 5a — dos modelos de Django en `_get_country_pricelist_multi`

`res.country` e `ir.config_parameter` siguen siendo modelos de Django (la
app `base` está pendiente de `BaseModel`), y `env[...]` devuelve su clase,
sin `search` ni `get_param` de recordset. El país del contexto se busca con
su gestor (`ResCountry.objects.filter(code=...)`) y el parámetro con
`SystemParameter.get_param`; son las dos lecturas que la fuente hace en
`odoo19c: addons/product/models/product_pricelist.py:290` y `:300`. La
búsqueda de la tarifa por grupo de país (`country_group_ids.country_ids`)
sí va por el dominio del ORM, como en la fuente. `price` y `rule_tip` no se
almacenan, así que no hay migración.

Prueba: `tests/unit/product/test_product_pricelist_labels.py`.

Los nueve `onchange` de 5a, uno por uno (`odoo19c: addons/product/models/
product_pricelist_item.py`): `_onchange_base` (`:384`),
`_onchange_base_pricelist_id` (`:392`), `_onchange_compute_price` (`:398`),
`_onchange_display_applied_on` (`:416`), `_onchange_product_id` (`:434`),
`_onchange_product_tmpl_id` (`:445`), `_onchange_rule_content` (`:452`),
`_onchange_price_round` (`:469`) y `_onchange_validity_period` (`:474`).
Prueba: `tests/unit/product/test_product_pricelist_labels.py`.
