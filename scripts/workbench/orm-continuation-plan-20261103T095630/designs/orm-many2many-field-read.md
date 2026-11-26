# Many2many.read como lectura del campo (orm-many2many-field-read-0485)

Dependencia de `designs/ir-filters-port-19.md`: `get_filters` hace
`search_read` con `user_ids` entre los campos, y `_fetch_query` lee cada campo
sin columna con `field.read(fetched)` (`src/orm/models.py:10990`).

## Referencia

`odoo19c: odoo/orm/fields_relational.py:1370-1410` — `Many2many.read`:
comodelo con `active_test=False` más el contexto del campo; la consulta de las
líneas con `comodel._search(domain, order=comodel._order,
bypass_access=filter_access)`; `JOIN` con la tabla de relación
(`column2 = comodel.id`) y `column1 IN ids`; agrupa por registro; si se
saltó el acceso en la búsqueda, filtra los corregistros con
`_filtered_access('read')`; guarda con `_insert_cache` una tupla por
registro, en el orden de `records._ids`.

## Estado heredado (medido)

- `models.Field.read = _field_read` (`src/orm/fields.py:4975`) es la guarda de
  la fuente: un campo sin columna levanta `NotImplementedError`. Ningún
  `read` propio para `ManyToManyField` (`grep "def read" src/orm/fields_relational.py`
  → 0). `search_read` de un `Many2many` de un `BaseModel` revienta:
  `NotImplementedError: Method read() undefined on base.IrFilters.user_ids`.
- La fila `orm-many2many-read-reference-0485` del plan verificó la lectura por
  el descriptor (el accesor de Django), no por `field.read`.
- El comodelo puede ser un modelo de Django sin `_search`: `res.users`
  (sonda: `hasattr(ResUsers, '_search')` → `False`; orden `partner__name,
  login`).

## Cambio

`_many2many_read(self, records)` instalado como `ManyToManyField.read`, junto
a `write_real`/`write_new`:

- **Comodelo `BaseModel`:** el cuerpo de la fuente, con `Query.add_join`,
  `add_where`, `select` y `env.execute_query`, y el dominio de
  `_multi_comodel_domain`.
- **Comodelo de Django:** la misma relación leída de la tabla intermedia
  (`through`), con `column1 IN ids`, ordenada por el orden del comodelo
  (`_meta.ordering` a través de la FK de destino) y sin filtro de activos,
  que es el `active_test=False` de la fuente. Su acceso es el del gestor
  base, como el resto de lecturas de modelos de Django en este árbol.

## Pruebas

- `tests/unit/orm/test_many2many_field_read.py`: `search_read` de
  `ir.filters` con `user_ids` devuelve los ids en el orden del comodelo y una
  tupla vacía sin usuarios; un comodelo `BaseModel`
  (`utm.campaign.tag_ids` → `utm.tag`) devuelve sus ids por `field.read`.

## Anulación

Retirar la instalación (`ManyToManyField.read` vuelve a `_field_read`): caen
exactamente los casos que leen por `field.read`.

## Adenda: `convert_to_read` y la forma de la caché de un comodelo de Django

- `_RelationalMulti.convert_to_read` (`odoo19c: fields_relational.py:668-669`,
  `return value.ids`) no estaba portado: `read()` de un `Many2many` devolvía
  el `QuerySet` crudo. Se porta en `_RelationalMulti`, que lo instala en los
  dos dueños (`One2many` y `ManyToManyField`) como la fuente lo hereda en
  ambos; un comodelo de Django entrega su `QuerySet`, y sus claves salen en su
  orden.
- La caché de un comodelo de Django guarda su `QuerySet`
  (`_many2many_convert_to_cache`), así que la rama de Django de `read`
  inserta uno por registro, en el orden del comodelo.
- psycopg 3 no adapta la tupla de `IN %s`: se usa `= ANY(%s)` con lista,
  la convención declarada en `src/orm/fields.py:5571-5573`.

## Medido

- `tests/unit/orm/test_many2many_field_read.py`: 2 passed; antes del código,
  2 failed con `NotImplementedError: Method read() undefined on …`.
- Anulación (sin `ManyToManyField.read = _many2many_read`): caen exactamente
  los 2 casos de este archivo y los 2 de `ir.filters` que leen `user_ids`
  (`get_filters` y el dominio web); 23 sobreviven. Restaurada con `cmp`.

## `_overrides_search`

≙ `type(comodel)._search is not BaseModel._search`
(`odoo19c: odoo/orm/fields_relational.py:1376-1377`), la condición de
`filter_access`. `orm.models` importa `fields_relational`, así que `BaseModel`
no se nombra en este archivo: la clase que define el `_search` efectivo se
busca en el MRO del comodelo. La ejercita la rama `BaseModel` de
`tests/unit/orm/test_many2many_field_read.py` (`utm.tag`, sin `_search`
propio: no se salta el acceso).
