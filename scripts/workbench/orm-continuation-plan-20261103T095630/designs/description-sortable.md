# `Field._description_sortable` por el mecanismo de la referencia

Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`,
`odoo/orm/fields.py:909-922`.

## Contrato

Ordenable si: almacenado con columna (atajo); o el campo heredado lo es; o
`model._order_field_to_sql(model._table, name, SQL(), SQL(), query)` no lanza
`ValueError` ni `AccessError`. Consumidor: `fields_get` (`sortable`), que
lee el cliente web.

## Kaupamex antes del cambio

Divergencia de mecanismo declarada: respondía por `concrete`. Hasta que
`_order_field_to_sql` existió (`db29e327`) y `_field_to_sql` recorrió los
`related` no almacenados (`267ade99`), las dos respuestas coincidían. Ahora
no: `test_orm.related.foo_name` (`related='foo_id.name'`) es ordenable en la
fuente y aquí respondía `False`.

## Decisión

El mecanismo de la fuente para los modelos con `_as_query` (`BaseModel`).
Divergencia declarada que se conserva: un modelo de Django que no es
`BaseModel` no tiene `_as_query` y responde por la columna.

## Pruebas

`tests/unit/orm/test_description_sortable.py`: columna almacenada → `True`;
`related` no almacenado → `True`; calculado sin columna → `False`.
Controles: volver a responder por la columna tumba el `related`; no capturar
`ValueError` tumba el calculado.
