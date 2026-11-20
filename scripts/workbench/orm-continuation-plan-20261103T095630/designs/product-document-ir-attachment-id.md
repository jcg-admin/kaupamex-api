# `product.document.ir_attachment_id`: el enlace de `_inherits` con su nombre

Unidad `product-document-ir-attachment-id-0122` (TASK-API-0122), parte del
sucesor `product-fk-names-0122`.

## Contrato medido en la referencia

`odoo19c: addons/product/models/product_document.py:11-16` declara
`_inherits = {'ir.attachment': 'ir_attachment_id'}` y
`ir_attachment_id = fields.Many2one('ir.attachment', ..., required=True,
ondelete='cascade')`. El puerto llamaba al campo `ir_attachment`, y delegaba
en él los campos del adjunto.

## Cambios

1. `ProductDocument.ir_attachment` → `ProductDocument.ir_attachment_id`, en
   forma C. Migración sin SQL en `sqlmigrate`.
2. Las propiedades de delegación (`name`, `type`, `url`, `mimetype`,
   `res_model`, `res_id`) y los dos métodos que leen el adjunto pasan a
   `self.ir_attachment_id`.
3. `ProductDocument.clean` (`if not self.ir_attachment_id`) y
   `ProductDocument.delete` (`self.ir_attachment if self.ir_attachment_id
   else None`) comprueban hoy la presencia con el `attname` entero. Tras el
   cambio, `ir_attachment_id` es el registro, y en un FK obligatorio sin
   asignar leerlo lanza en vez de dar `None`: la presencia pasa a
   `ir_attachment_id_id`.
4. Censo y `scripts/fk_naming_baseline.txt`.

## Símbolos que cambian

- `ProductDocument.ir_attachment_id`
  (`odoo19c: addons/product/models/product_document.py:16`);
- `ProductDocument.name`, `ProductDocument.type`, `ProductDocument.url`,
  `ProductDocument.mimetype`, `ProductDocument.res_model`,
  `ProductDocument.res_id`, `ProductDocument.clean`,
  `ProductDocument.delete`: leen el nombre de la fuente; la conducta no
  cambia;
- la migración `0037_document_ir_attachment_id`.

## Pruebas

`tests/unit/product/test_product_document_ir_attachment_id.py`: nombre y
columna; un documento delega nombre y tipo en su adjunto; borrar el
documento borra su adjunto; `clean` de un documento sin adjunto asignado no
lanza. Control de anulación: devolver la guarda de `clean` a leer el
registro hace caer exactamente la última.
