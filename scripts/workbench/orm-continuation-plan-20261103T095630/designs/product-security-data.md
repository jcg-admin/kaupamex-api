# La seguridad de `product` se carga por su manifiesto

Creado: 2026-11-20T13:19:27 (UTC). TASK-API-0397. Precedente:
`designs/security-data-by-manifest.md`.

## Contrato de la referencia

`odoo19c: addons/product/__manifest__.py:28-31` declara en `data`
`security/product_security.xml` y `security/ir.model.access.csv`, y los
carga el ciclo de instalación con los modelos vivos.

- `product_security.xml` declara un privilegio
  (`res_groups_privilege_product`, categoría `base.module_category_master_data`),
  tres grupos (`group_product_pricelist`, `group_product_variant`,
  `group_product_manager`, este último implicado por `base.group_system`,
  con `base.user_root` y el privilegio), el enlace de `base.user_admin` al
  gestor y seis `ir.rule` `noupdate` de empresa (`product_comp_rule`,
  `product_document_comp_rule`, `product_pricelist_comp_rule`,
  `product_pricelist_item_comp_rule`, `product_supplierinfo_comp_rule`,
  `product_combo_comp_rule`).
- `ir.model.access.csv`: 38 filas.

## Estado medido

- El manifiesto de `addons/product` no declara `data`.
- Existen en el árbol `base.module_category_master_data`, `base.group_user`,
  `base.group_partner_manager`, `base.group_system`, `base.user_root` y el
  modelo `res.groups.privilege` (`src/addons/base/data/res_groups_data.py`,
  `src/addons/base/models/res_groups_privilege.py`). `base.user_admin` no.
- Los 16 modelos de `product` derivan de `TimeStampedModel`, pero adoptan
  el `AccessManager` (`orm/model_classes.py::adopt_access_manager`), cuyo
  `check_access` aplica la ACL y luego las reglas (`AccessQuerySet._check_access`).
  Las filas cargadas se aplican a esas consultas aunque el modelo no sea
  `BaseModel`. La aplicación implícita en `_search` llega con la adopción de
  `BaseModel` (siguiente unidad, `basemodel-adoption-product-attribute-value-0397`).
- El XML-ID `product.model_<nombre>` lo recibe todo modelo con `_name`
  propio del módulo (`IrModel._update_model_xmlids`). 15 de 16 lo declaran;
  `ProductDocument` no, y la fuente sí
  (`odoo19c: addons/product/models/product_document.py:9-14`).

## Decisión

1. Copia fiel de los dos archivos en `addons/product/security/`, declarados
   en `data`. Omisiones, declaradas en la cabecera del XML:
   - el registro `base.user_admin` (no existe en este árbol, DEC-3);
   - cinco filas del CSV cuyo modelo no tiene XML-ID aquí:
     `access_product_template_attribute_exclusion`,
     `access_product_template_attribute_exclusion_manager`
     (`product.template.attribute.exclusion` sin portar),
     `access_product_label_layout_user` (asistente sin portar),
     `access_update_product_attribute_value_manager` (asistente sin portar) y
     `access_uom_uom_product_manager` (la extensión de `uom.uom` de
     `product/models/uom_uom.py` sin portar: sin ella `product.model_uom_uom`
     no existe).
   Quedan 33 filas.
2. `ProductDocument` gana su cabecera completa, verbatim: `_name`,
   `_description`, `_inherits = {'ir.attachment': 'ir_attachment_id'}` y
   `_order`. Medido al cargar el XML: el cargador valida el dominio de cada
   regla, y `product_document_comp_rule` cita `company_id`, que el documento
   sólo tiene por `_inherits`. Con él, la regla valida.
3. `product.pricelist.item` gana `company_id` y `currency_id`
   (`odoo19c: product_pricelist_item.py:31-32`, calculados y almacenados,
   `_compute_company_id`/`_compute_currency_id` en `:170-183`).
   Medido igual: `product_pricelist_item_comp_rule` no valida sin
   `company_id`. Se calculan en `save()` (precedente `product.combo.item`)
   y la migración `0043` los rellena en las filas existentes. La lectura de
   la moneda de la compañía va por `currency`, nombre que el puerto da hoy
   a `res.company.currency_id`.
   `_check_company_auto` y los tres `check_company=True` de la regla
   quedan en el sucesor `pricelist-item-check-company-0397`.

## Sucesores

- `product-document-delegation-0397`: retirar las propiedades escritas a
  mano de `product.document` que `_inherits` ya delega.
- `pricelist-item-check-company-0397`: `_check_company_auto` y
  `check_company` de `product.pricelist.item`.
- `res-company-currency-id`: nombre de la fuente de la moneda de
  `res.company`.
- `product-uom-uom-extension-0397`: `product/models/uom_uom.py`
  (`product_uom_ids`) y su fila de ACL.
- `product-template-attribute-exclusion-0397`: modelo y sus dos filas.
- Asistentes `product.label.layout` y `update.product.attribute.value` con
  sus filas.

## Pruebas

`tests/unit/product/test_product_security.py`: los grupos y el privilegio
con su XML-ID y sus implicaciones; las 33 filas y las seis reglas con su
XML-ID; un usuario interno lee `product.template` y no lo escribe; un gestor
lo escribe; la regla de empresa oculta una plantilla de otra empresa; una
regla de tarifa guarda la compañía y la moneda de su tarifa o de su
plantilla.
Anulación: retirar los dos archivos de `data` hace caer las pruebas.

## Símbolos que cambia

- `addons/product/__manifest__.py` (`data`), `security/product_security.xml`
  y `security/ir.model.access.csv`;
- `ProductDocument` (`_name`, `_description`, `_inherits`, `_order`);
- `ProductPricelistItem.company_id`, `currency_id`, `save`,
  `_compute_company_id` y `_compute_currency_id`;
- la migración `0043_pricelist_item_company_currency`, que añade las dos
  columnas y las rellena con el cómputo de la fuente
  (`odoo19c: product_pricelist_item.py:170-183`).

Pruebas: `tests/unit/product/test_product_security.py`. Control de
anulación, medido: retirados los dos archivos de `data` (y purgadas de la
base de prueba las filas que ya habían creado), caen exactamente las cinco
pruebas que dependen de ellos (5 failed, 3 passed); sobreviven la cabecera
del documento y los dos cómputos de la regla de tarifa.
