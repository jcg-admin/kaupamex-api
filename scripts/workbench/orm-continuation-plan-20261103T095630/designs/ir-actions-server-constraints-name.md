# ir.actions.server: restricciones y nombre calculado (5c)

Unidad: `ir-actions-server-constraints-name-0391` (TASK-GEN-0391; depende de
`ir-actions-server-model-id-0391`).

## Contrato medido en la referencia

| Símbolo | Fuente | Forma |
|---|---|---|
| `name`, `automated_name` | `odoo19c: odoo/addons/base/models/ir_actions.py:605-606` | `Char(compute='_compute_name', store=True, readonly=False)` y `Char(compute='_compute_name', store=True)` |
| `_compute_name` | `odoo19c: odoo/addons/base/models/ir_actions.py:843-849` | `@api.depends(lambda self: self._name_depends())`, bucle sobre `self` |
| `_check_python_code` | `odoo19c: odoo/addons/base/models/ir_actions.py:960-965` | `@api.constrains('code')`, `self.sudo().filtered('code')`, `test_python_expr(... mode="exec")` |
| `_check_children` | `odoo19c: odoo/addons/base/models/ir_actions.py:967-973` | `@api.constrains('parent_id', 'child_ids')`, `self._has_cycle()`, mensajes en inglés con `_()` |

## Lo que el puerto tiene hoy

- `automated_name` es un `Char` plano; `name` lo hereda de `IrActionsBase`
  sin `compute`. `_compute_name` opera sobre un registro y lo invoca
  `save()` a mano.
- `_check_python_code` y `_check_children` no llevan `@api.constrains`; los
  invoca `save()`. `_check_children` recorre `parent_id` a mano en lugar de
  `_has_cycle()` y sus mensajes están en español.

## Cambio

1. `name` y `automated_name` en `IrActionsServer` con `compute`, `store=True`
   (y `readonly=False` en `name`), sin cambiar columna.
2. `_compute_name` con `@api.depends(lambda self: self._name_depends())` y
   bucle `for action in self`; `_name_depends` como método de instancia.
3. `_check_python_code` con `@api.constrains('code')` y bucle sobre
   `self.sudo().filtered('code')`.
4. `_check_children` con `@api.constrains('parent_id', 'child_ids')`,
   `self._has_cycle()` y los mensajes de la fuente vía `self.env._`.
5. `save()` deja de invocar los tres; se retira si queda vacío.

## Pruebas

- RED: crear por el ORM una acción con `state` y sin `name` da el nombre
  generado; cambiar `state` lo regenera; un ciclo `parent_id` levanta
  `ValidationError('Recursion found in child server actions')`; código con
  sintaxis rota levanta al crear y al escribir.
- Consumidores a medir: `test_ir_actions_server_naming.py`,
  `test_ir_actions_constraints.py` y todo creador por `objects.create`
  (el `save()` directo de Django deja de validar, como en 4d).

## Medido

| Símbolo | Archivo | Fuente |
|---|---|---|
| `IrActionsServer.name` (`compute='_compute_name'`, `store=True`, `readonly=False`) y `IrActionsServer.automated_name` (`compute='_compute_name'`, `store=True`) | `src/addons/base/models/ir_actions.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:605-606` |
| `IrActionsServer._compute_name` con `@api.depends(lambda self: self._name_depends())` y bucle sobre `self` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:843-849` |
| `IrActionsServer._check_python_code` con `@api.constrains('code')` sobre `self.sudo().filtered('code')` | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:960-965` |
| `IrActionsServer._check_children` con `@api.constrains('parent_id', 'child_ids')`, `self._has_cycle()` y los mensajes de la fuente | ídem | `odoo19c: odoo/addons/base/models/ir_actions.py:967-973` |
| se retira `IrActionsServer.save`: el ORM dispara el cómputo y las restricciones | ídem | `odoo19c: odoo/orm/models.py:4683-4685` |
| migración `0152_alter_iractionsserver_automated_name`: `automated_name` pasa a `editable=False` (sólo estado) | `src/addons/base/migrations/0152_alter_iractionsserver_automated_name.py` | `odoo19c: odoo/addons/base/models/ir_actions.py:606` |
| migración `0153_compute_ir_actions_server_automated_name`: calcula `automated_name` sobre las filas existentes con `ComputeStoredFields`, como toda columna calculada que entró por `AddField` (lo exige `tests/unit/orm/test_new_computed_columns_are_computed.py`) | `src/addons/base/migrations/0153_compute_ir_actions_server_automated_name.py` | `odoo19c: odoo/orm/models.py:3220-3238` |

Medido al implementar: `_name_depends` sigue siendo `classmethod`, porque el
`depends` invocable del puerto se llama con la clase del modelo (la misma
convención que `_warning_depends`); como método de instancia, la carga de
módulos murió con `TypeError` (616 errores de montaje en el primer
subconjunto).

Dar `name` en `create` protege todo su grupo calculado, `automated_name`
incluido (`odoo19c: odoo/orm/models.py:4683-4685`, `field_computed`): en la
fuente `automated_name` no se calcula en ese caso. La prueba heredada que lo
esperaba calculado se corrigió a la conducta de la fuente.

Prueba: `tests/unit/base/test_ir_actions_server_constraints_name.py`, 7 casos
(RED: 4 de 7; los otros 3 pasaban por el `save()` que se retira). Los
consumidores que validaban por `objects.create`/`save()` pasan a
`create`/`write` del ORM.

Anulación (copia restaurada y comparada con `cmp`): sin el `@api.depends` y
sin los dos `@api.constrains` caen exactamente 14 casos, todos de las cuatro
pruebas que miden el nombre y las dos restricciones.

Subconjunto derivado (45 archivos): `612 passed, 2 xfailed`; el único rojo es
`test_default_get::test_a_model_with_name_resolves_to_name`, preexistente y
dependiente del orden.
