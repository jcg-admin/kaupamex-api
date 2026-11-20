# Ordenar por un campo heredado por `_inherits`

Creado: 2026-11-20T16:51:24 (UTC). TASK-API-0122 (destapado por la etapa 1 de
`product-variant-cluster.md`).

## Contrato de la referencia

`odoo19c: odoo/orm/models.py:5262-5291` (`_order_field_to_sql`) delega en
`odoo19c: odoo/orm/models.py:2910-2934` (`_field_to_sql`): un campo
`related` no almacenado se recorre con `_traverse_related_sql`, que añade
el join. Un campo heredado por `_inherits` es exactamente eso
(`related='product_tmpl_id.name'`, sin almacenar), así que
`product.product` con `_order = 'default_code, name, id'` ordena por el
`name` de la plantilla a través de `product_tmpl_id`.

## Estado medido

`orm.models.order_to_django` ya recorre un `related` sin columna. Pero la
entrada que `model_field_registry(ProductProduct)` da para `name` es el
`CharField` del padre (`column='name'`, `related='product_tmpl_id_id.name'`):
al tener columna cae a `F('name')` sobre la tabla del hijo y Django levanta
`FieldError: Cannot resolve keyword 'name'`. Medido: 16 fallos en la etapa 1
(lectura de `product_variant_ids`, cuyo comodelo ordena por `_order`).

## Decisión

En `order_to_django`, un campo cuyo modelo dueño es un padre declarado en
`_inherits` del modelo se ordena por el camino de la clave de delegación
(`<fk>__<campo>`), con la dirección y los nulos del término: es el join que
la fuente añade. No cambia el registro de campos.

## Pruebas

`tests/unit/orm/test_order_by_inherited_field.py`: `order_to_django`
sobre `product.product` con `name` devuelve el camino por
`product_tmpl_id`; ordenar variantes por `_order` respeta el nombre de la
plantilla. Anulación: sin la rama, cae la prueba con `FieldError`.
