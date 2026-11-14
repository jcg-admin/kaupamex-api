# hr.employee.location sobre BaseModel

Unidad: `basemodel-adoption-hr-employee-location-0397` (TASK-API-0397).

## Contrato medido en la referencia

`odoo19c: addons/hr_homeworking/models/hr_homeworking.py` (28 líneas,
`models.Model`):

| Símbolo | Línea | Aquí antes | Aquí después |
|---|---|---|---|
| clase sobre `models.Model` | :8 | `TimeStampedModel` | `models.BaseModel, TimeStampedModel` |
| `work_location_name` related | :13 | property | `fields.Char(related=…, store=False)` |
| `work_location_type` related | :14 | property | `fields.Selection(related=…, store=False)` |
| `employee_id` default `env.user.employee_id` | :15 | no portado (divergencia 2) | `default=_default_employee` (usuario del entorno) |
| `employee_name` related | :16 | property | `fields.Char(related=…, store=False)` |
| `day_week_string` / `_compute_day_week_string` | :18, :25-28 | property con `date_format(…, 'l')` | compute con `tools.format_date(env, date, date_format='EEEE')` |

La divergencia 3 (`format_date` ausente en `src/tools`) ya no se sostiene:
`src/tools/misc.py:1388` porta `format_date`. Se retira.

Seguridad (`hr_homeworking/security/`), cargada en el manifiesto como en
la fuente:

- `ir.model.access.csv`: `hr.group_hr_user` y `base.group_user`, 1/1/1/1.
- `security.xml`: `homeworking_own_rule` (`employee_id = user.employee_id.id`,
  `base.group_user`) y `homeworking_admin_rule` (`[(1,'=',1)]`,
  `hr.group_hr_user`). `user.employee_id` ya lo evalúan las reglas de `hr`.

## Casos (RED)

1. el modelo deriva de `BaseModel`;
2. los tres related siguen su ruta (ya pasaba como property; queda como
   control de que el cambio de forma no los rompe);
3. `day_week_string` = `format_date(env, date, date_format='EEEE')`;
4. sin `employee_id`, `create` toma el empleado del usuario que actúa;
5. un usuario interno sólo ve sus filas (regla own);
6. un oficial de RR. HH. ve todas (regla admin).

## Anulación

- retirar `_default_employee` del campo: cae exactamente el caso 4;
- retirar `security.xml` del manifiesto: cae el caso 5.

## Medición

- 6 de 6 en verde sobre la base reconstruida con `--create-db`.
- Retirar `default=_default_employee`: cae exactamente el caso 4 (5 pasan).
- Retirar `security/security.xml` del manifiesto (con `--create-db`, porque
  la seguridad se carga al migrar): cae exactamente el caso 5 (5 pasan). El
  caso 6 sobrevive, y es lo esperado: sin reglas el oficial también lo ve
  todo; mide el CSV de accesos, no la regla admin.
