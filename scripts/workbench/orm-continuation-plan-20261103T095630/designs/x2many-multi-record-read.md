# Lectura de un x2many sobre varios registros

Unidad: requisito de C2 de `restrict-ondelete-partial-reconcile.md`
(`orm-fk-delete-policy-contract-0515`). Revisión de partida: `07d92374`.

## Fuente

`odoo19c: odoo/orm/fields_relational.py:42` — `_Relational.__get__`: con
`len(records._ids) <= 1` delega en `Field.__get__`; con más, lee el valor
de cada registro y devuelve `convert_to_record_multi(vals, records)`.

`odoo19c: odoo/orm/fields_relational.py:655` —
`_RelationalMulti.convert_to_record_multi`: los ids de cada valor, en el
orden de los registros, sin repetir (`unique`), como recordset del
comodelo; si el comodelo tiene campo de activo y `active_test` no está
apagado, se filtran los archivados.

## Medición

`tests/unit/orm/test_x2many_multi_record_read.py`, cinco casos, sobre
`07d92374`: los cinco fallan con `ValueError: Expected singleton`. Son las
tres rutas de lectura:

| Ruta | Dónde | Caso |
|---|---|---|
| inverso que Django crea de un Many2one | `_x2many_descriptor_get`, `src/orm/models.py` | `(first + second).lines` de `test_orm.multi` |
| `Many2many` | la misma función (el descriptor es subclase) | `(first + second).tags` |
| `One2many` declarado | `One2many.__get__`, `src/orm/fields_relational.py` | `(first + second).messages` de `test_orm.discussion` |

La rama equivalente del `Many2one` ya está portada (`_forward_get`).

Quién lo pide: `remove_move_reconcile`
(`odoo19c: addons/account/models/account_move_line.py:3138`) hace
`(self.matched_debit_ids + self.matched_credit_ids).unlink()` sobre el
conjunto de apuntes de un asiento.

## Cambio

Dos funciones en `src/orm/fields_relational.py`, que es donde la fuente
tiene `_Relational.__get__` y de donde `src/orm/models.py` ya importa (el
sentido inverso sería un ciclo):

- `_x2many_union(records, read_one)` lee cada registro con la lectura
  singular que ya existe y devuelve el recordset del comodelo con los ids
  en orden y sin repetir. Si algún valor no es un recordset (comodelo de
  Django), llama a `records.ensure_one()`: la lectura sigue siendo la de un
  registro.
- `_reads_x2many_union(instance, comodel)` es la condición de la rama: el
  dueño tiene más de un id y el comodelo tiene recordset
  (`odoo19c: odoo/orm/fields_relational.py:44`, `len(records._ids) <= 1`).

`_x2many_descriptor_get` las llama con el comodelo ya resuelto;
`One2many.__get__` llama a `_x2many_union` con más de un id, antes de sus
ramas de cómputo y de `related`, porque el comodelo de esas dos ramas sólo
se conoce al leer.

- La lectura singular ya resuelve por registro el cómputo pendiente, el
  registro de `new()`, el dominio del campo y el filtro de activos, así que
  la unión no los repite.
- Comodelo de Django (sin recordset): no cambia; sigue la lectura de un
  registro.

**Divergencia de mecanismo, declarada:** sin caché por campo ni `fetch`,
se hace una lectura por registro; la fuente lee la caché y trae en lote lo
que falta. Mismo límite que `_read_one2many` ya declara.

## Pruebas y anulaciones

Los cinco casos de arriba. Anulación: retirada la rama de
`_x2many_descriptor_get` caen los tres del inverso y el del `Many2many`;
retirada la de `One2many.__get__` cae el del declarado; sin `unique` cae
`test_many2many_is_the_union_without_duplicates`.

*Métrica:* ids del recordset devuelto contra los de leer registro por
registro.
*Ciega a:* la caché, `fetch` y el filtro `active_test` de la unión.
