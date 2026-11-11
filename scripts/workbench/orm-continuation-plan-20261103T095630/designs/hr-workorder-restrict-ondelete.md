# Entradas de trabajo y órdenes de trabajo: ondelete='restrict' por defecto

Fecha: 2026-11-11T06:47:59. Cuarto tramo de la población de 93. TASK-API-0515.

## Contrato de la fuente (odoo-tools `abe4040ec1`)

| Campo | Declaración | Defecto |
|---|---|---|
| `hr.work.entry.employee_id` | `addons/hr_work_entry/models/hr_work_entry.py:25`, `required=True` | `restrict` |
| `hr.work.entry.version_id` | `:26`, `required=True` | `restrict` |
| `hr.user.work.entry.employee.employee_id` | `addons/hr_work_entry/models/hr_user_work_entry_employee.py:13`, `required=True` | `restrict` |
| `mrp.workorder.production_id` | `addons/mrp/models/mrp_workorder.py:44`, `required=True` | `restrict` |

Modelos `models.Model`, sin `ondelete` (`fields_relational.py:274-282`).

## Estado previo

Los cuatro `CASCADE`: borrar un empleado o una versión borraba sus
entradas de trabajo; borrar una orden de fabricación, sus órdenes de
trabajo.

## Implementación y verificación

Los cuatro a `PROTECT`; migraciones `hr_work_entry/0004_restrict_ondelete_required`
(×3) y `mrp/0003_restrict_ondelete_required` (×1), sólo estado;
`CORRECTED` gana las cuatro filas.

**Desviación del orden TDD, declarada.** El cambio se implementó antes de
escribir las pruebas de conducta. El RED se demuestra por anulación: con
cada campo de vuelta en `CASCADE`, su caso de conducta falla (además de
su fila paramétrica). Ese es el mismo veredicto que un RED previo, pero se
registra que no hubo una ejecución en rojo anterior a la implementación.

Aislamiento: en el caso del empleado, la entrada usa la versión de **otro**
empleado, porque una versión propia también apunta al empleado medido.

| Mutación | Cae |
|---|---|
| `HrWorkEntry.employee` → `CASCADE` | exactamente su caso de conducta y su fila paramétrica |
| `HrWorkEntry.version` → `CASCADE` | ídem |
| `HrUserWorkEntryEmployee.employee` → `CASCADE` | ídem |
| `MrpWorkorder.production` → `CASCADE` | ídem |

Suites de la unidad: 20 passed, 83 xfailed. Población: 93 filas, 12
corregidas, 81 pendientes.
