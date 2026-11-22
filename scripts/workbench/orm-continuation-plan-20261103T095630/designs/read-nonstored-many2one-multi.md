# read-nonstored-many2one-0397 — `Many2one` calculado sin columna sobre varios registros

## Referencia

`odoo19c: odoo/orm/fields_relational.py:42-79` — `_Relational.__get__`: con
varios registros lee cada valor de la caché y devuelve
`convert_to_record_multi(vals, records)`, un recordset del comodelo.

## Defecto medido

`BaseModel._read_field` elige el descriptor por `attname` y sólo vuelve a
`field.name` ante `StoredMany2oneIdDescriptor`. En un `Many2one` **sin
columna**, Django fija `attname = '<nombre>_id'`, y el ORM instala allí el
`ComputedFieldDescriptor`, que devuelve el **id**; el registro lo da
`NonStoredMany2oneAccessor` en `field.name`. Por eso
`_read_relational_multi` recibe enteros y `_relation_value_ids` levanta
`AttributeError: 'int' object has no attribute 'pk'`.

Sonda (2026-11-22): `_read_field(root_id)` sobre dos planes devolvió
`<class 'int'> 285` en los dos. Latente también en
`purchase.order.line.selected_seller_id` (mismo par de descriptores).

## Cambio

En `BaseModel._read_field`, cuando `attname` difiere de `field.name` —sólo
pasa en un `Many2one`— el descriptor que se usa es el de `field.name`, que
entrega el corecord. Cubre la rama almacenada (`StoredMany2oneIdDescriptor`)
y la calculada sin columna con una sola condición.

## Prueba

`tests/unit/orm/test_read_nonstored_many2one_multi.py`, sobre
`test_orm.category.root_categ`: `mapped` sobre dos categorías devuelve el
recordset de sus raíces; un registro solo sigue leyendo su corecord. Rojo
antes del cambio: `1 failed, 1 passed` (el caso de varios).

| Símbolo | Referencia |
|---|---|
| `BaseModel._read_field` | `odoo19c: odoo/orm/fields_relational.py:42-79` |
