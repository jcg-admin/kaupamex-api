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

## Pendiente de medir antes de implementar

- Si `fields.Char(compute=..., store=True)` en una subclase de un abstracto
  que ya declara `name` genera migración (no debe).
- Si el recómputo almacenado del ORM dispara en `create` y `write` con
  `depends` por lambda (precedente: `_compute_warning` en 5b, no almacenado).
