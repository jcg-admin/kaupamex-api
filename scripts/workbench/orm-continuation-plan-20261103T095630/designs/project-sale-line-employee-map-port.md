# Porte completo de `project.sale.line.employee.map`

Fuente: `odoo19c: addons/sale_timesheet/models/project_sale_line_employee_map.py`
(odoo-tools `abe4040ec1`). Puerto: `addons/sale_timesheet/models/
project_sale_line_employee_map.py`.

## La base `TimeStampedModel` es correcta

La fuente declara `models.Model`, y la metaclase le añade el log-access
(`odoo/orm/models.py:287-292`). `TimeStampedModel` es el equivalente del
puerto: reúne las cuatro columnas del log-access con los mixins que la
fuente tiene en `BaseModel` (nombre visible, orden, chequeo de empresa,
archivado). No hay divergencia en la base; la deuda está en los símbolos.

## Lo que el docstring del puerto declara bloqueado, medido de nuevo

| Dependencia | Docstring del puerto | Hoy (2026-11-12) |
|---|---|---|
| `sale.order.line.order_partner_id` | 0 hits | **existe** (`addons/sale/models/sale_order_line.py:250`) |
| `sale.order.line.currency_id` | «no declara `currency`» | **existe** (`:237`, related a la orden) |
| `account.analytic.line.so_line` | no existe | **existe** (`addons/sale/models/analytic.py`) |
| `sale.order.line._sellable_lines_domain` | 0 hits | sigue ausente |
| `project.project.sale_order_id` / `sale_line_id` | los declara `sale_project` | siguen ausentes |
| `project.project.is_template` | 0 hits | sigue ausente |
| `project.project._update_timesheets_sale_line_id` | ausente | sigue ausente |

Tres bloqueos declarados ya no lo son: el docstring es estado heredado
incorrecto y se corrige al portar.

## Orden del porte (TRAE / CONSTRUYE)

1. **Campos calculados y almacenados con el mecanismo del ORM** (TRAE: el
   ORM ya porta `compute`/`store`/`depends`/`inverse`): `price_unit`,
   `currency_id` (desde `sale_line.currency_id`, como la fuente), `cost`,
   `is_cost_changed`, `display_cost` con su `inverse`. Retira el receptor
   `pre_save` y las funciones de módulo que hoy los sincronizan.
2. **`related`**: `company_id`, `partner_id`, `cost_currency_id`; y
   `sale_order_id` cuando exista `project.project.sale_order_id`.
3. **`existing_employee_ids`**: Many2many calculado, no `property`.
4. **`_compute_sale_line_id` y `_domain_sale_line_id`**: exigen
   `_sellable_lines_domain` en `addons/sale` (CONSTRUYE, en su hogar) y
   `project.project.sale_line_id`.
5. **`create`/`write` → `_update_project_timesheet`**: exige
   `project.project._update_timesheets_sale_line_id`, que escribe
   `so_line`, ya disponible.

Los pasos 4 y 5 dependen de piezas de `project`/`sale_project` y de
`sale` que este diseño no porta; son su condición de cierre. Los pasos 1-3
se pueden hacer con lo que ya existe.

*Métrica:* `grep` de cada símbolo en `addons/` y `src/`, sin pruebas.
*Ciega a:* que un símbolo presente tenga el comportamiento de la fuente;
eso lo deciden las pruebas de cada paso.

## `display_cost` y su inverso: dependencias medidas (2026-11-12)

La fuente (`addons/sale_timesheet/models/project_sale_line_employee_map.py`,
odoo-tools `abe4040ec1`) declara `display_cost` como Monetary **no
almacenado** con `compute`/`inverse`, `@api.depends('cost',
'employee_id.resource_calendar_id')` y `@api.depends_context('company')`. La
conversión a costo diario depende de
`env.ref('uom.product_uom_day') == env.company.timesheet_encode_uom_id` y de
`resource.calendar.hours_per_day` leído con `_read_group`.

| Dependencia | Estado en el árbol | Fuente de verdad |
|---|---|---|
| `hr.employee.resource_calendar_id` | **existe** (el docstring del puerto dice que no: estado heredado incorrecto) | registro de modelos, medido |
| `res.company.timesheet_encode_uom_id` | existe (`addons/hr_timesheet/models/res_company.py`) | ídem |
| `resource.calendar.hours_per_day` | **property**, no columna; la fuente lo declara `store=True, compute='_compute_hours_per_day', readonly=False` (`resource/models/resource_calendar.py:102`) | `_read_group` sobre él no es posible |
| `uom.product_uom_day` | **ausente**: el manifiesto de `uom` no declara `data` y `uom_data.xml` (31 registros) no está portado; `env.ref` no lo resuelve | `addons/uom/__manifest__.py` |

Consecuencia: el porte fiel de `display_cost` exige antes dos piezas de
otros addons, las dos del contrato de la fuente:

1. **`uom_data.xml`** (LGPL-3, copia y adaptación): los campos de sus
   registros (`name`, `relative_factor`, `relative_uom_id`, `active`)
   coinciden con `uom.Uom`, `decimal.precision` existe en `base`, y el
   cargador ya procesa `data` de un manifiesto (`src/modules/loading.py:90`,
   usado por `hr` y `hr_skills`). Cierra también el default de
   `timesheet_encode_uom_id`, que hoy busca `name='Hours'` y resuelve `None`.
2. **`resource.calendar.hours_per_day`** como calculado almacenado editable.

Sin la primera, un `env.ref('uom.product_uom_day')` con su
`raise_if_not_found=True` de la fuente rompería toda lectura de
`display_cost`; con `False` compararía `None == None` cuando la compañía no
tiene unidad y tomaría la rama de días. Ninguna de las dos es el contrato.

Orden: `uom_data.xml` → `hours_per_day` → `display_cost`/`_inverse_display_cost`
→ `existing_employee_ids` (Many2many calculado sobre
`project.sale_line_employee_ids.employee_id`).

*Métrica:* registro de modelos tras `django.setup()` y lectura de la fuente.
*Ciega a:* el comportamiento de `convert_file` con `noupdate="1"` y
`forcecreate`, que se mide al portar el XML.
