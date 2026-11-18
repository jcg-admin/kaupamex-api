# `uom.uom` sobre `BaseModel`

Creado: 2026-11-18T13:45:06 (UTC). TASK-API-0397, unidad hija de
`basemodel-adoption-0397` (`designs/basemodel-adoption-program.md`).
Referencia: odoo-tools `abe4040ec1`, Odoo 19 Community.

## El contrato de la fuente

`odoo19c: addons/uom/models/uom_uom.py:17-76`:

| Campo | Fuente | Aquí, antes |
|---|---|---|
| `sequence` | `compute='_compute_sequence', store=True, readonly=False, precompute=True` (`:35`, cómputo `:53-60`) | entero; `save()` lo fija si vale 0 |
| `rounding` | `compute='_compute_rounding'` no almacenado (`:39`, `:62-67`) | `property` |
| `related_uom_ids` | `One2many('uom.uom', 'relative_uom_id')` (`:42`) | sólo el `related_name='related_uoms'` de la FK |
| `factor` | `compute='_compute_factor', recursive=True, store=True` (`:43`, cómputo `:69-75`) | `save()` lo calcula y vuelve a guardar a cada hijo |

Un cómputo almacenado corre con `compute_sudo`, que vale `store` por
defecto (`odoo19c: odoo/orm/fields.py:448`, aplicado en
`odoo19c: odoo/orm/fields.py:1900-1901`). La propagación de `factor` a los
hijos no pasa por la ACL del usuario.

ACL: `addons/uom/security/ir.model.access.csv`, dos filas, ya portada
(cargada por el `data` del manifiesto).

## Medido al adoptar

Con la base cambiada a `(models.BaseModel, TimeStampedModel)` y
`related_uom_ids` declarado, el bucle manual de `save()` lee los hijos
por el ORM con la ACL del usuario actual: 140 errores `PermissionDenied`
en los consumidores (`stock`, `uom`, `sale`). Es el síntoma de lo que la
fuente no hace, propagar a mano, y no un defecto de la ACL.

## Decisión

Porte fiel de los cuatro campos:

1. `related_uom_ids` declarado; la FK lleva `related_name='+'`.
2. `factor` = cómputo recursivo almacenado con `@depends('relative_factor',
   'relative_uom_id', 'relative_uom_id.factor')`: el ORM propaga como
   superusuario, y desaparecen el cálculo y el bucle de `save()`.
3. `sequence` = cómputo almacenado editable con `precompute`, que no pisa
   un valor ya puesto (`:53-60`).
4. `rounding` = cómputo no almacenado.

`save()` conserva sólo lo que no es cómputo: `clean_business` y
`parent_path`. Lo que `BaseModel` ya mantiene, `parent_path` con
`_parent_store`, se mide antes de retirarlo de `save()`.

## RED

- `Uom` es `BaseModel`; `uom` sale de `PENDING` en
  `tests/unit/orm/test_basemodel_reach.py`.
- Cambiar el `relative_factor` de un padre recalcula el `factor` de los
  nietos, sin superusuario en el entorno.
- `sequence` se deriva al crear y no se pisa al cambiar el factor.

## Ejecución (2026-11-18)

- `Uom(models.BaseModel, TimeStampedModel)`; `related_uom_ids`, `factor`
  (`_compute_factor` ≙ `odoo19c: addons/uom/models/uom_uom.py:70`),
  `sequence` (`_compute_sequence` ≙ `odoo19c: addons/uom/models/uom_uom.py:54`)
  y `rounding` (`_compute_rounding` ≙ `odoo19c: addons/uom/models/uom_uom.py:62`)
  con la forma de la fuente; `save()` conserva `clean_business` y
  `parent_path`. Migración `addons/uom/migrations/0009_uom_on_basemodel.py`:
  en la base sólo cae el `CHECK` de entero positivo de `sequence`.
- **Lo que la adopción destapó en un consumidor.** `stock.rule._run_pull`
  crea los movimientos como superusuario en la fuente
  (`odoo19c: addons/stock/models/stock_rule.py:312-313`, *"the current user
  may not have the rights to do it"*); el porte no lo hacía y, con la ACL de
  `uom` activa, el usuario sin grupo no podía leer `factor`. Se porta con
  `orm.environments.sudo`.
- **Premisa de una prueba.** `account.move.line.product_uom_id` sin producto
  es ahora un recordset vacío, no `None`, como en la fuente;
  `test_the_uom_is_none_without_a_product` pasa a
  `test_the_uom_is_empty_without_a_product`.
- Pruebas: `tests/unit/uom/test_uom_basemodel.py`
  (`test_uom_is_a_basemodel`, `test_the_children_are_a_declared_one2many`,
  `test_a_parent_factor_reaches_the_grandchildren`,
  `test_the_sequence_is_derived_once`); `uom` sale de `PENDING` en
  `tests/unit/orm/test_basemodel_reach.py`.
- Anulación: sin el cómputo de `factor` caen 19 de 29 pruebas de `uom` (toda
  la conversión, que lee `factor`): no queda otra vía que lo calcule.
- Consumidores derivados (pruebas que nombran `uom`, `Uom`, `stock_rule`,
  `StockRule` o `_run_pull`): 1291 passed.

### Símbolos por archivo (para `check_reference_flow`)

- `StockRule._run_pull` ≙ `odoo19c: addons/stock/models/stock_rule.py:313`:
  crea los movimientos dentro de `sudo()`. Prueba:
  `tests/integration/sale/test_stock.py` (`test_run_pull_make_to_stock`,
  que con la ACL de `uom` activa fallaba con `PermissionDenied`).
- `0009_uom_on_basemodel` ≙ `odoo19c: addons/uom/models/uom_uom.py:35`
  (`sequence` como `Integer`): retira el `CHECK` de entero positivo y pasa
  `factor`, `sequence` y `relative_uom_id` a su forma nueva. Prueba:
  `tests/unit/uom/test_uom_basemodel.py`.
