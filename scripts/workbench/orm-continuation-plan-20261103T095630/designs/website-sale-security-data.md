# La seguridad de `website_sale` se carga por su manifiesto

Creado: 2026-11-20T17:12:07 (UTC). TASK-API-0397. Unidad
`website-sale-security-data-0397`, previa a cerrar la etapa 1 de
`product-variant-cluster.md` (la API de carrito responde 403 sin ella).
Precedentes: `designs/security-data-by-manifest.md`,
`designs/product-security-data.md`.

## Contrato de la referencia

`odoo19c: addons/website_sale/__manifest__.py:13-17` carga
`security/ir.model.access.csv` (66 filas: lectura del catálogo para
`base.group_public`, `base.group_portal` y `base.group_user`, gestión para
`sales_team.group_sale_manager`), `security/ir_rules.xml` (seis registros:
el catálogo público sólo publicado y vendible, las reglas de tarifa por
sitio web, las categorías públicas vacías) y `security/res_groups.xml`
(tres grupos de función y dos enlaces `implied_ids`).

## Estado medido

- El manifiesto de `addons/website_sale` no declara `data`.
- De las referencias del CSV no tienen XML-ID aquí siete modelos de
  `website_sale` sin portar (`product.feed`, `product.image`,
  `product.public.category`, `website.base.unit`, `website.checkout.step`,
  `website.sale.extra.field`, `product.ribbon`),
  `product.model_product_template_attribute_exclusion` (etapa 3 del grupo),
  `sale.model_product_attribute_custom_value` (la extensión de `sale` sin
  portar) y los grupos `website.group_website_designer` y
  `website.group_website_restricted_editor` (la seguridad de `website` sin
  portar). Quedan 35 filas.
- `ir_rules.xml` necesita lo que el puerto no tiene: `product.template`
  expone `is_published` pero no `website_published`, y el contexto de
  evaluación de `ir.rule` no publica `website`.

## Decisión

1. `security/ir.model.access.csv` (las 35 filas, copia fiel) y
   `security/res_groups.xml` (los tres grupos de función y el enlace de
   `base.group_user` a `account.group_delivery_invoice_address`), en
   `data`. Omitidos, declarados en la cabecera del XML: las filas de arriba y
   el enlace de `sales_team.group_sale_manager` a
   `website.group_website_restricted_editor`.
2. `security/ir_rules.xml` queda para el sucesor
   `website-sale-ir-rules-0397`: exige `website_published` en la plantilla
   (`website.published.mixin`) y `website` en el contexto de las reglas.

## Pruebas

`tests/unit/website_sale/test_website_sale_security.py`: las filas y los
grupos con su XML-ID; un usuario público y uno de portal leen
`product.template` y `product.product` y no los escriben. Anulación:
retirar los archivos de `data` (y purgar sus filas de la base de prueba)
hace caer las pruebas que dependen de ellos.
