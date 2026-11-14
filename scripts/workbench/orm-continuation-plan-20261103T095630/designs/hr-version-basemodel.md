# `hr.version` sobre `BaseModel`

Creado: 2026-11-14T12:03:40 (UTC). TASK-API-0397. Segundo tramo de
`basemodel-adoption-hr-core-0397`.

## Búsqueda previa

Adopción de `BaseModel` (REUSE). La ACL de `hr.version` ya la carga el
manifiesto de `hr` y coincide con la fuente (dos filas, `group_hr_user` y
`group_hr_manager`).

## Medido aquí (`b74051db`)

Probar la base nueva rompió 41 casos de `tests/unit/hr`: siete métodos de
`HrEmployee` (`hr_employee.py`: `versions_count`, `_get_first_versions`,
`_get_version`, `_compute_current_version_id`, `_get_all_contract_dates`,
`_get_versions_with_contract_overlap_with_period`, `create_contract`,
once llamadas) usan la inversa `versions` con la API de `QuerySet`
(`filter`, `order_by`, `values_list`, `distinct`, `count`), y con
`hr.version` sobre `BaseModel` esa inversa es un recordset.

## Decisión

1. Base `models.BaseModel` primero.
2. Esos métodos consultan por el gestor (`_version_rows()` →
   `HrVersion.objects.filter(employee=self)`), que conserva su semántica
   exacta, inactivas incluidas. Reescribirlos sobre el recordset cambiaría
   qué versiones ven.
3. Tests: escriben bajo superusuario; la longitud de la inversa por `len`;
   un Many2one vacío (`employee.version`, `version.resource_calendar`) es
   un recordset vacío y no `None`, como en la fuente.

## RED y anulación

Los tres casos (es `BaseModel`; un interno no lee versiones; un oficial de
RR. HH. sí) se escribieron tras la base nueva: con la base anterior caen
los tres.
