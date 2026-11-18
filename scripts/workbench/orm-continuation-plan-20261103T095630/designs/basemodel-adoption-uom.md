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
