# Diseño — `_inherits` con varios padres (TASK-API-0182)

Fecha: 2026-11-09T00:28:50 · rama `feature/vm-x2hokp-orm-root` · referencia odoo-tools@abe4040ec1.

## Contrato medido en odoo19c

- `odoo/orm/models.py:407-425` — `_inherits` admite varios padres
  (`{'a.model': 'a_field_id', 'b.model': 'b_field_id'}`). Con nombres
  repetidos, *"the inherited field will correspond to the last one (in the
  inherits list order)"*.
- `odoo/orm/model_classes.py:480-508` (`_add_inherited_fields`) — un dict
  por comprensión recorre los padres en orden: el último sobrescribe el
  nombre. Un campo redefinido en el hijo no se hereda.
- `odoo/orm/models.py:4692-4707` — `create` crea o escribe cada padre,
  en el orden de `_inherits`, como el usuario del entorno.
- Censo: **0** modelos de odoo19c declaran más de un padre (recorrido AST
  sobre `odoo/` y `addons/`). La referencia no ofrece un modelo que
  ejecutar; el contrato sale del atributo y de `_add_inherited_fields`.

## Divergencia esperada aquí (por leer, no medida todavía)

`apply_inherits` (`src/orm/inherits.py`) se llama una vez por padre desde
`ensure_inherits`, y en cada llamada sobrescribe `_inherits_fields`,
`__getattr__`, `__setattr__` y `save` con el cierre de ese padre. El
segundo padre anularía al primero. Hay que confirmarlo con una prueba RED
antes de cambiar nada.

## Modelo de prueba propio (no existe en la referencia)

`test_orm.related_inherits_two` en `src/addons/test_orm/models/test_orm.py`
más su migración:

```python
_inherits = {'test_orm.related': 'base_id',
             'test_orm.related_bar': 'bar_parent_id'}
base_id = fields.Many2one('test_orm.related', required=True, ondelete='cascade')
bar_parent_id = fields.Many2one('test_orm.related_bar', required=True, ondelete='cascade')
```

| Caso | Esperado (contrato) |
|---|---|
| `foo_id`, sólo del padre A | se lee y escribe por el hijo, va a A |
| `active`, sólo del padre B | se lee y escribe por el hijo, va a B |
| `name`, en A y en B | gana B (el último): lectura y escritura van a B |
| campo propio del hijo | precede a los heredados |
| `create` sin padres | crea A y B con sus valores |
| `create` con un padre dado | escribe el dado, crea el otro |
| reglas y ACL | cada padre se comprueba con su propio modelo |
| `ensure_inherits` dos veces | sin envoltorios dobles, sin recursión |
| persistencia | cada valor queda en la tabla de su padre |

## Orden de trabajo

1. Modelo y migración (después de que termine la puerta multidb de
   `c5e9ed15`, que lee el árbol de trabajo).
2. Prueba RED con los casos de la tabla.
3. Corregir `apply_inherits` y `DelegatedFieldNames` para varios padres.
4. Controles de anulación, suite derivada, settlement.
