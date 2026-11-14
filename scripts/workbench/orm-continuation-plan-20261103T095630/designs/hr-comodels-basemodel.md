# Los comodelos pequeños de `hr` sobre `BaseModel` (grupo B, primer tramo)

Creado: 2026-11-14T11:45:26 (UTC). TASK-API-0397. Unidad `basemodel-adoption-hr-comodels-0397`.

## Búsqueda previa

Adopción de `BaseModel` (REUSE, mismo patrón que las unidades de
hr_recruitment y hr_work_entry). Seguridad: ya la carga el manifiesto de
`hr` (`security/ir.model.access.csv`); las 7 filas de estos cinco modelos
son idénticas a las de la fuente (`diff` vacío contra
`odoo19c: hr/security/ir.model.access.csv`).

## Contrato

`odoo19c: addons/hr/models/{hr_payroll_structure_type,hr_contract_type,
hr_employee_category,hr_departure_reason,hr_work_location}.py`: los cinco
son `models.Model`.

## Medido aquí (`f9163cc1`)

Los cinco derivaban sólo de `TimeStampedModel`. Consumidores en tests:
`tests/unit/hr` (9 archivos) y `tests/unit/orm` (`test_translated_char`,
`test_copy`). El primero de `orm` escribe `hr.departure.reason` sin
superusuario; mide la traducción, no el acceso, así que escribe bajo sudo.

## RED y anulación

RED 10 de 10: los cinco son `BaseModel`, y un usuario interno no puede
crearlos (ninguna fila concede `create` a `base.group_user`). Anulación:
las cinco clases de vuelta a `TimeStampedModel` → caen exactamente los 10.

## Lo que esta unidad no cierra

El resto del grupo B: `hr.department`, `hr.version`, `hr.employee.public`
(`basemodel-adoption-hr-core-0397`, a registrar en el plan).
