# `product.attribute.value` completo, sobre `BaseModel`

Creado: 2026-11-20T14:10:29 (UTC). TASK-API-0122 / TASK-API-0397. Unidad
`product-attribute-value-complete-0122`. Reúne `basemodel-adoption-product-attribute-value-0397`
y `pav-unlink-guard-0122` (sucesores de `ptav-source-names.md` y
`product-security-data.md`): la guarda de borrado necesita `BaseModel`
(`@api.ondelete`, `action_archive`, recordsets) y la adopción sin los campos
de la fuente sería un porte parcial.

## Contrato (`odoo19c: addons/product/models/product_attribute_value.py`)

Cabecera `:12-14`. Campos `:19-58`: `name` (required, translate),
`sequence` (index), `attribute_id` (cascade, index), `pav_attribute_line_ids`
(M2M sobre `product_attribute_value_product_template_attribute_line_rel`,
copy=False), `default_extra_price`, `is_custom`, `html_color`,
`display_type` (related `attribute_id.display_type`), `color` (default
`_get_default_color`, randint 1-11), `image` (70x70), `active`,
`is_used_on_products` y `default_extra_price_changed` (calculados).
Métodos: `_get_default_color`, `_compute_display_name`,
`_compute_is_used_on_products`, `_compute_default_extra_price_changed`,
`write` (rehúsa cambiar el atributo de un valor usado; invalida al
resecuenciar), `check_is_used_on_products`,
`_unlink_except_used_on_product`, `unlink` (archiva el valor usado sólo por
variantes archivadas), `_without_no_variant_attributes`,
`action_add_to_products`, `action_update_prices`.

## Estado del puerto (medido 2026-11-20)

`TimeStampedModel` con `attribute_id` (`related_name='values'`, sin
consumidores medidos por grep), `name`, `sequence`
(`PositiveIntegerField`) y una `UniqueConstraint(attribute_id, name)` que
la fuente no declara. La cara `pav_attribute_line_ids` ya existe como
inversa de `ProductTemplateAttributeLine.value_ids`. PTAV
`product_attribute_value_id` es PROTECT (divergencia declarada en
`ptav-source-names.md`, se resuelve aquí a CASCADE).

Medido: la `UniqueConstraint(attribute_id, name)` del puerto no existe ni en
`odoo19c:` ni en `odoo18c:` (`product_attribute_value.py` de los dos árboles
sin `_sql_constraints` ni `models.Constraint`): es invención y se retira.

Disponibles en el árbol: `ProductProduct.product_template_attribute_value_ids`
con `related_name='ptav_product_variant_ids'` (la rama de archivo de
`unlink`), `orm.fields_binary.Image`, `BaseModel.action_archive` y
`@api.ondelete` (precedente `account.account`). La ACL de lectura para
`base.group_user` y la de gestión para `group_product_manager` la cargó
`5b8f7fea`.

## Decisión

1. `ProductAttributeValue(models.BaseModel, TimeStampedModel)`, patrón de
   `uom.uom` (`designs/basemodel-adoption-uom.md`).
2. Los catorce campos con la forma de la fuente. `attribute_id` lleva
   `related_name='value_ids'`, el nombre del One2many de la fuente en
   `product.attribute` (`odoo19c: product_attribute.py`); `values` no tiene
   lectores medidos. `sequence` pasa a `Integer` indexado (sale el `CHECK`
   de `PositiveIntegerField`). `name` sin `translate`: el almacenamiento
   jsonb es TASK-GEN-0060, abierta, y se declara en el campo.
3. Los once métodos, verbatim en su lógica: `_compute_display_name` (con
   `show_attribute`), los dos cómputos, `write` (guarda del atributo e
   invalidación al resecuenciar), `check_is_used_on_products`,
   `_unlink_except_used_on_product`, `unlink` (archiva el valor que sólo
   usan variantes archivadas), `_without_no_variant_attributes` y las dos
   acciones, que devuelven el diccionario de la fuente aunque el asistente
   `update.product.attribute.value` no esté portado (sucesor declarado en
   `product-security-data.md`).
4. Se retira la `UniqueConstraint` inventada.
5. PTAV `product_attribute_value_id` pasa de PROTECT a CASCADE
   (`odoo19c: product_template_attribute_value.py:27-30`): la guarda que
   justificaba la divergencia existe ya. Corregido al medir:
   `test_many2many_ondelete` borra una PTAV usada por una variante (el
   `restrict` de la combinación), no un valor, y no cambia.

## Medido al implementar

- Los tres comodelos que recorren los métodos (`product.template.attribute.line`,
  `product.template.attribute.value`, `product.product`) son aún
  `TimeStampedModel`: `env[...]` devuelve su clase de Django. Los cuerpos
  conservan la lógica y el orden de la fuente y leen esas filas por su
  manager (el dominio de empresa compilado con `orm.domains.to_q`).
  Divergencia de mecanismo declarada en el módulo; sucesor
  `basemodel-adoption-product-chain-0397`.
- PTAV no tiene aún el `product_tmpl_id` almacenado de la fuente (su porte
  completo es sucesor de `ptav-source-names.md`):
  `_compute_default_extra_price_changed` llega a la plantilla por
  `attribute_line_id`.
- `_get_default_color` queda a nivel de módulo, como en `crm.tag`: Django
  serializa el `default` por ruta de import y lo llama sin instancia.
  Registrada en `scripts/divergencias_declaradas.txt`.
- `default_extra_price` lleva `default=0.0`: un `Float` vacío de la fuente
  se lee `0.0`, y con `NULL` el flag de cambio salía verdadero en un valor
  recién creado. Los otros opcionales (`is_custom`, `html_color`, `image`)
  admiten `NULL` como la columna de la fuente.
- Leer el valor pasa por la ACL: las pruebas de `tests/unit/product` y
  `tests/integration/product` corren como superusuario
  (`conftest.py`, precedente `tests/unit/fleet/conftest.py`, ≙
  `TransactionCase`); `test_product_security.py` redefine el fixture
  porque mide la ACL.
- Las dos pruebas que leían `str(valor)` leen `display_name` (la fuente no
  declara `__str__`), y la de unicidad prueba que la fuente no la declara.

## Símbolos que cambia

`addons/product/models/product_attribute_value.py` (la clase entera),
`ProductTemplateAttributeValue.product_attribute_value_id`, los dos
`conftest.py` de producto, `scripts/divergencias_declaradas.txt` y la migración
`0044_product_attribute_value_complete` (columnas nuevas, `sequence`,
`related_name`, retirada de la restricción, `on_delete` de PTAV).

## Pruebas

`tests/unit/product/test_product_attribute_value_complete.py`: es
`BaseModel`; los campos y su cabecera; `display_name` con y sin
`show_attribute`; `is_used_on_products`; borrar un valor usado levanta
`UserError` con los productos; un valor usado sólo por variantes archivadas
se archiva; cambiar el atributo de un valor usado se rehúsa; un valor sin
uso se borra y arrastra sus PTAV. Anulación: retirar
`_unlink_except_used_on_product` hace caer la prueba de la guarda.
