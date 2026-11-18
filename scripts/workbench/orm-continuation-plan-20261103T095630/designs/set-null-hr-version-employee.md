# `hr.version.employee_id`: borrar un empleado deja sus versiones

Unidad: `orm-fk-delete-policy-contract-0515` (TASK-API-0515), fila
`hr.HrVersion.employee`, apartada del bloque D hasta medir el borrado bajo
`_inherits`. Escrito el 2026-11-18 durante la F2 de `7c4235f0`.

## Contrato de la referencia (medido)

| Símbolo | Cita | Contrato |
|---|---|---|
| `hr.version.employee_id` | `odoo19c: addons/hr/models/hr_version.py:54-59` | `Many2one('hr.employee')`, no obligatorio, sin `ondelete`: `set null` (`odoo19c: odoo/orm/fields_relational.py:274-282`) |
| `hr.employee._inherits` | `odoo19c: addons/hr/models/hr_employee.py:43` | `{'hr.version': 'version_id'}` |
| `hr.employee.version_id` | `odoo19c: addons/hr/models/hr_employee.py:46-54` | calculado, `store=False`: no hay columna ni FK del empleado a la versión |
| `hr.employee.unlink` | `odoo19c: addons/hr/models/hr_employee.py:1473-1476` | `super().unlink()` y luego borra los recursos; no toca las versiones |
| `_unlink_except_last_version` | `odoo19c: addons/hr/models/hr_version.py:294-300` | guarda al borrar **versiones**, no empleados |

Borrar un empleado deja sus versiones con `employee_id` vacío. Aquí hoy se
borran (`CASCADE`, `addons/hr/models/hr_version.py:171-175`).

## Cambio

`HrVersion.employee`: `on_delete=models.SET_NULL` (ya es `null=True`).
Migración `0021_set_null_version_employee` de `hr`.

No se porta aquí `_unlink_except_last_version`: es otra obligación, del
borrado de versiones, y nuestro `hr_version.py` la declara ausente en su
cabecera. Sigue como sucesor.

## Prueba

- Fila del contrato en `tests/unit/orm/test_delete_policy_contract.py`.
- `tests/unit/hr/test_version_survives_employee_delete.py`: borrar un
  empleado deja su versión en la base con `employee` nulo.

Anulación: devolver el campo a `CASCADE` tumba la fila y el caso.

*Métrica:* la fila de `hr_version` leída tras borrar el empleado.
*Ciega a:* qué hacen `hr_work_entry` y `hr_skills` con una versión sin
empleado; lo dirá la F2.
