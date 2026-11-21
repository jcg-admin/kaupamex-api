# product.document a BaseModel

Unidad `product-document-basemodel-0397`, tramo product. Referencia
`odoo19c: addons/product/models/product_document.py` (60 líneas).

## Estado heredado medido

`ProductDocument` era Django con `TimeStampedModel`, delegación a mano por
propiedades (`name`, `type`, `url`, `mimetype`, `res_model`, `res_id`), la
validación de la URL en `clean()` y el borrado del adjunto en `delete()`. La
prosa decía que `create` con contexto y `copy_data` no se portaban porque
«Django no tiene contexto de ORM propagable» ni «operación de copiar
registro». Las dos frases son falsas hoy: `BaseModel` tiene `with_context`
y `copy`, e `IrAttachment` ya es `BaseModel`.

## Implementación

- `addons/product/models/product_document.py`: `ProductDocument` deriva de
  `(models.BaseModel, TimeStampedModel)` con el `_inherits` del ORM, así que
  crear el documento crea su adjunto y los campos del adjunto se leen y
  escriben desde el documento. Métodos de la fuente:
  `ProductDocument._onchange_url`
  (`odoo19c: addons/product/models/product_document.py:26-33`),
  `ProductDocument.create` (`:38-42`), `ProductDocument.copy_data`
  (`:44-55`) y `ProductDocument.unlink` (`:57-60`). Se retiran las
  propiedades de delegación, `ProductDocument.clean` y
  `ProductDocument.delete`.
- **Migración 0057** `addons/product/migrations/0057_document_basemodel.py`:
  sólo metadatos de campo.
- `ProductDocument.for_record` se conserva: es el `domain` del `One2many`
  `product_document_ids` de la plantilla y la variante.

## Lo que destapó el porte en el ORM

`new()` en un modelo con `_inherits` perdía los valores de los campos
heredados: `_update_cache` los escribe en la caché del registro, pero
leerlos iba al delegado, que en un registro nuevo es otro registro nuevo sin
ellos. En la fuente el campo heredado es un `related` del propio modelo y su
lectura devuelve la caché (`odoo19c: odoo/orm/models.py:6441-6460`). Ahora
`src/orm/inherits.py` lee primero la caché propia cuando el registro es
nuevo (`_cached_inherited_value`). Sin esto `_onchange_url` no podía ver la
URL de un formulario.

## Premisas de prueba que cambian

`tests/unit/product/test_product_document_ir_attachment_id.py` borraba con
el `delete()` de Django; el contrato de la fuente es `unlink`.

## Pruebas

`tests/unit/product/test_product_document_basemodel.py`: el adjunto que se
crea, copia y borra con el documento, la lectura delegada, y la URL inválida
rechazada en el `onchange` de un registro nuevo.

## Lo que este tramo no cierra

`product_document_ids` de la plantilla y la variante
(`odoo19c: addons/product/models/product_template.py:164-168`,
`odoo19c: addons/product/models/product_product.py:81-85`) es un `One2many`
sobre `res_id`, un `Many2oneReference`, con `domain` sobre `res_model`. El ORM
no tiene todavía un `One2many` cuyo inverso sea un `Many2oneReference`;
hasta entonces son propiedades que llaman a `for_record`. Sucesor:
`product-document-ids-0397`.
