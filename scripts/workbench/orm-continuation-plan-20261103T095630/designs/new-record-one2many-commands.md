# Comandos sobre un `One2many` declarado en un registro de `new()`

Unidad sucesora registrada por `ir-actions-server-model-id-0391`
(`designs/ir-actions-server-model-id.md`, «Hallazgo: el x2many de un registro
de `new()`»). TASK-API-0397.

## Contrato medido en la referencia

- `odoo19c: odoo/orm/models.py` (`new`, `_update_cache`): `new(values)` llama
  a `field.convert_to_cache(value, self, validate)` y a
  `field._update_cache(self, value)` para cada valor.
- `odoo19c: odoo/orm/fields_relational.py:589-641`
  (`_RelationalMulti.convert_to_cache`): los comandos sobre un registro sin id
  dan `NewId(origin)` de las líneas; `:576-586` (`_update_cache`).
- `odoo19c: odoo/orm/fields.py:1715-1734` (`Field.__get__`): un registro nuevo
  con origen lee de `record._origin` el valor que no tiene en caché, salvo un
  calculado de sólo lectura.
- `odoo19c: odoo/addons/base/models/ir_actions.py:761-799`
  (`_get_warning_messages`): lee `self.child_ids` sin condición; la guarda
  `if self.model_id` (`:765`) sólo es alcanzable en un registro del
  formulario.

## Lo que el puerto tenía

1. `One2many` declarado sin `convert_to_cache`: `new({'child_ids': [(6, 0,
   ids)]})` levantaba `AttributeError`.
2. El protocolo común de caché que `orm/fields.py` instala en `One2many`
   escribía en la caché propia del objeto declarado, mientras
   `One2many.__get__` lee la de la relación inversa de Django: las líneas se
   perdían.
3. `StoredMany2oneIdDescriptor.__get__` devolvía `None` para un registro
   nuevo sin valor en caché, sin consultar `_origin`; el descriptor escalar ya
   tenía esa rama.
4. `_get_warning_messages` leía las hijas sólo `if self.pk`: el `pk` de un
   `NewId` es falso.

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `_one2many_inverse_rel`, `_one2many_convert_to_cache` y `One2many.convert_to_cache` | `src/orm/fields_relational.py` | `odoo19c: odoo/orm/fields_relational.py:589-641` |
| `_one2many_update_cache` y `One2many._update_cache`, instalados después del protocolo común | `src/orm/fields.py` | `odoo19c: odoo/orm/fields_relational.py:576-586` |
| `StoredMany2oneIdDescriptor.__get__`: rama del origen | `src/orm/fields.py` | `odoo19c: odoo/orm/fields.py:1715-1734` |
| `IrActionsServer._get_warning_messages`: las hijas sin la guarda del `pk` | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:761-799` |

Prueba: `tests/unit/orm/test_new_one2many_commands.py`, 5 casos (RED: 3 de 3
de los iniciales, por `AttributeError`).

Anulación, cada pieza por separado (copias restauradas y comparadas con
`cmp`):

| Pieza retirada | Casos que caen |
|---|---|
| `One2many.convert_to_cache` | 4 de 5 |
| `One2many._update_cache` | 2 de 5 |
| la rama del origen | 1 de 5 (la hija del mismo modelo) |
| la lectura de hijas sin `pk` | 1 de 5 (el control con `model_id`) |

La rama del origen no la discriminaba ningún caso hasta añadir el de la hija
del mismo modelo: con `model_id` leído como vacío, una hija de otro modelo
«difiere» igual.
