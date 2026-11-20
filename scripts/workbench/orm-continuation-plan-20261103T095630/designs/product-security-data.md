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
2. `ProductDocument` gana `_name`, `_description` y `_order`, verbatim.
   `_inherits` activa la delegación de campos y de dominio
   (`orm/inherits.py`, `orm/domains.py:1273`) y sustituye las propiedades
   escritas a mano: es la unidad sucesora `product-document-inherits-0397`.

## Sucesores

- `product-document-inherits-0397`: `_inherits` de `product.document`.
- `product-uom-uom-extension-0397`: `product/models/uom_uom.py`
  (`product_uom_ids`) y su fila de ACL.
- `product-template-attribute-exclusion-0397`: modelo y sus dos filas.
- Asistentes `product.label.layout` y `update.product.attribute.value` con
  sus filas.

## Pruebas

`tests/unit/product/test_product_security.py`: los grupos y el privilegio
con su XML-ID y sus implicaciones; las 33 filas y las seis reglas con su
XML-ID; un usuario interno lee `product.template` y no lo escribe; un gestor
lo escribe; la regla de empresa oculta una plantilla de otra empresa.
Anulación: retirar los dos archivos de `data` hace caer las pruebas.
