# `hours_per_day` y `hours_per_week` como calculados almacenados editables

TASK-GEN-0241, antecede a `employee-map-display-cost-0241`. Autoridad:
odoo-tools `abe4040ec1`.

## Contrato de la fuente

`resource/models/resource_calendar.py`:

- `:102` `hours_per_day = fields.Float(store=True, compute=..., digits=(2, 2),
  readonly=False)` y `:104-106` `hours_per_week` (`store=True,
  readonly=False, copy=False`);
- `:210-221` los dos cálculos, `@api.depends('attendance_ids',
  'attendance_ids.hour_from', 'attendance_ids.hour_to', 'two_weeks_calendar',
  'flexible_hours')`, filtran `not flexible_hours` y redondean a 2 decimales
  (`float_round(..., precision_digits=2)`): un calendario flexible conserva el
  valor que su usuario escribió;
- `:703-707` `_get_hours_per_day` = horas por semana / días por semana.

`hr_work_entry/models/resource_calendar.py:9-12` extiende
`_compute_hours_per_week` sólo para añadir
`attendance_ids.work_entry_type_id.is_leave` a sus dependencias, y filtra los
tramos de ausencia en `_get_global_attendances`.

`sale_timesheet` lee `hours_per_day` con `_read_group` (por eso exige columna)
para convertir el costo por hora en costo por día.

## Lo que hay hoy, y por qué no satisface el contrato

Las dos son `property` (`addons/resource/models/resource_calendar.py:65-70`,
`:255-260`): no se almacenan, no se pueden editar, no redondean, y un
calendario flexible devuelve 0 en vez de su valor. `hr_work_entry` no puede
extender un cálculo que no existe y su docstring lo declara.

Consumidores medidos (13 líneas fuera del modelo): `hr_version.py:725-728`
(salario por hora), `resource_calendar_attendance.py:165-166` (umbral de media
jornada), `project_sale_line_employee_map.py:296-315` (costo por día) y la
documentación de `hr_work_entry`. Todos leen el atributo por nombre, que se
conserva.

## Diseño

1. Dos `fields.Float` almacenados, `readonly=False`, con los cálculos y las
   dependencias de la fuente sobre `attendances` (el `related_name` del
   `ForeignKey` de `resource.calendar.attendance`), filtrando flexibles y
   redondeando a 2 decimales.
2. Migración que añade las dos columnas y una migración de datos que calcula
   las filas existentes con el cálculo del modelo, no con una copia del cuerpo
   (frontera «calculados almacenados sobre filas existentes»).
3. `hr_work_entry` instala su extensión con `wrap_method`
   (`@api.depends('attendances.work_entry_type.is_leave')`), que la fusión de
   dependencias de designs/extension-depends-merge.md ya hace efectiva.

## Pruebas previstas (RED primero)

- editar un tramo recalcula y almacena los dos valores (lectura por
  `values_list`, no por el atributo);
- un valor escrito a mano en un calendario flexible se conserva;
- redondeo a 2 decimales (tramos de 7h20m en 3 días);
- cambiar `is_leave` del tipo de un tramo recalcula `hours_per_week`
  (control de la extensión) y su anulación con `setattr`;
- la migración de datos calcula las filas existentes.
