# Dominio de cada One2many sobre registros de `new()`

Referencia: odoo-tools `abe4040ec1a45beee90fb694e4eae4453e46b389`.

## Contrato

- `Many2one._update_inverses` (`odoo/orm/fields_relational.py:449-463`) recorre
  **cada** One2many inverso (`records.pool.field_inverses[self]`) y añade a su
  caché sólo `records.filtered_domain(invf.get_comodel_domain(corecord))`.
  La caché es **por campo**: `messages`, `important_messages` y
  `very_important_messages` de `test_orm.discussion` tienen cada uno la suya.
- `One2many.get_comodel_domain` (`:921-922`) = `domain` del campo más
  `_additional_domain`; un `domain` invocable se evalúa con el modelo
  (`:99-108`, caso `very_important_messages`).
- Consumidor de la referencia: `test_fields.py:2501-2514` (`test_60_one2many_domain`)
  y `:2536-2559` (`test_70_x2many_write`): las líneas no importantes no salen en
  `important_messages`; una línea importante sale en los tres.

## Kaupamex

- Dueño real: `_read_one2many` (`src/orm/fields_relational.py:2033`) ya busca
  con `field.get_comodel_domain(instance)`. Cumple.
- Dueño nuevo: `One2many.__get__` (`:522-534`) lee la caché de la relación
  inversa, **compartida** por los tres campos, y no aplica el dominio. Medido en
  H-API-1202/1203: `important_messages` de un dueño nuevo ve todas sus líneas.

## Decisión

No se separan las cachés por campo: en este árbol la caché del One2many es la
de la relación inversa (`field_data[inverse.remote_field]`), la que escriben
`_update_inverse` y `_write_new_one2many` y lee el descriptor del Many2one.
Partirla duplicaría la fuente de verdad. El dominio se aplica **al leer**, con
el mismo `get_comodel_domain` que usa `_read_one2many`:
`lines.filtered_domain(domain)` cuando el dominio no es trivial.

Divergencia declarada: la referencia filtra al insertar y su caché no se
reevalúa si la línea cambia después; aquí el filtro se evalúa en cada lectura,
como ya pasa con los dueños reales. Para el caso de inserción las dos dan lo
mismo.

## Pruebas (RED primero)

`tests/unit/orm/test_one2many_domain_on_new_records.py`, con `test_orm.discussion`
y `test_orm.message` de `new()`:

1. línea no importante → en `messages`, fuera de `important_messages` y de
   `very_important_messages` (dominio invocable);
2. línea importante → en los tres;
3. control positivo: `messages` sin dominio sigue viendo las dos.

Control de anulación: retirar el filtro hace caer 1 y deja 2 y 3.
