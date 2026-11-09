# `_field_to_sql` sobre un `related` no almacenado

Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`,
`odoo/orm/models.py` (`_field_to_sql`).

## Contrato

```
field = self._fields.get(fname)
if not field: raise ValueError("Invalid field ...")
if field.related and not field.store:
    model, field, alias = self._traverse_related_sql(alias, field, query)
    return model._field_to_sql(alias, related_expr, query)
self._check_field_access(field, 'read')
sql = field.to_sql(self, alias)
```

Un `related` no almacenado se resuelve **recorriendo** su camino (con los
JOIN de `_traverse_related_sql`); sólo un campo sin columna y sin `related`
falla, en `field.to_sql`.

## Kaupamex (medido)

`src/orm/models.py` `FieldSqlMixin._field_to_sql` rechaza `not concrete`
**antes** de la rama `related`. Un `related` no almacenado no es `concrete`,
así que nunca se recorre: `test_orm.related.foo_name`
(`related='foo_id.name'`) lanza `ValueError: Invalid field` en
`_field_to_sql`, y por eso también en `_order_field_to_sql`. En la referencia
el mismo campo produce la columna del modelo final.

## Decisión

Adelantar la rama del `related` no almacenado al rechazo por `concrete`. El
rechazo se conserva para el resto de campos sin columna, con su mensaje, que
`tests/unit/orm/test_fields_map_contract.py` fija (las relaciones inversas de
Django no tienen `related` de la referencia).

## Pruebas

`tests/unit/orm/test_field_to_sql_related.py` sobre `test_orm.related`:

1. `foo_name` (un salto) → columna `name` del alias unido de `foo_id`, y el
   JOIN en `query`;
2. `foo_bar_name` (dos saltos) → columna del segundo alias;
3. `_order_to_sql('foo_name desc')` ordena por esa columna;
4. un campo calculado no almacenado sin `related` (`test_orm.category.depth`)
   sigue fallando con `ValueError`.

Control de anulación: devolver el rechazo delante de la rama tumba 1-3 y deja 4.
