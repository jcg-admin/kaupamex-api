# basemodel-reverse-queryset-0397 — inversos de BaseModel leídos como queryset

Hija de `basemodel-adoption-0397`. Defecto latente de clase, medido.

## La regla, leída en el código

`_x2many_descriptor_get` (`src/orm/models.py`) devuelve un **recordset**
cuando la instancia dueña **y** el comodelo son `BaseModel`, y el gestor de
Django en cualquier otro caso. Es el contrato de la fuente: un One2many o un
Many2many de un registro es un recordset
(`odoo19c: odoo/orm/fields_relational.py`, `_RelationalMulti.__get__`). Un
recordset no tiene `filter`, `exclude`, `aggregate`, `values_list`,
`order_by`, `all`, `count` ni `first` (medido con `hasattr` sobre
`BaseModel`: sólo `exists`, `update`, `delete` y `create` coinciden de
nombre con el gestor). Cada adopción de `BaseModel` convierte en recordset
los inversos que entonces tienen dueño y destino `BaseModel`, y el código
escrito contra el gestor deja de funcionar sin que nada lo avise.

Confirmado por ejecución: `crm.team.assignment_max` (`crm_team.py:210`,
`self.crm_team_member_ids.all()`) muere con
`AttributeError: 'CrmTeamMember' object has no attribute 'all'`; los saldos
de la cuenta analítica, igual (corregidos en la unidad `company_id`).

## Inventario

Se obtuvo así: primero los nombres de accesor de todo `BaseModel` seguidos
de un método de queryset (`git grep`, 283 líneas). Un subagente de lectura
las clasificó por el receptor, y a su clasificación se le aplicaron dos
filtros medidos: que el método no exista en `BaseModel` y que el par
(dueño, accesor) tenga comodelo `BaseModel` (sonda sobre
`_meta.related_objects`). Quedan 40 sitios. Los seis `ProductProduct.route_ids`
quedan fuera: `ProductTemplate.route_ids` apunta a un modelo de Django.

```
addons/crm/models/crm_lead.py:792	CrmStage	['team_ids']
addons/crm/models/crm_lead.py:2310	CrmLead	['tag_ids']
addons/crm/models/crm_lead.py:3559	CrmLead	['tag_ids']
addons/crm/models/crm_lead.py:3605	CrmLead	['tag_ids']
addons/crm/models/crm_team.py:210	CrmTeam	['crm_team_member_ids']
addons/crm/models/crm_team.py:244	CrmTeam	['crm_team_member_ids']
addons/crm/models/crm_team.py:367	CrmTeam	['crm_team_member_ids']
addons/crm/models/crm_team.py:636	CrmTeam	['crm_team_member_ids']
addons/crm/models/crm_team.py:672	CrmTeam	['crm_team_member_ids']
addons/hr/models/hr_employee.py:1326	HrEmployee	['versions']
addons/hr/models/res_users.py:449	HrEmployee	['category']
addons/hr/models/resource.py:96	ResourceResource	['hr_hremployee_resource_mixin_set']
addons/hr/models/resource_calendar_leaves.py:87	ResourceResource	['hr_hremployee_resource_mixin_set']
addons/hr_fleet/models/employee.py:94	HrEmployee	['car_ids']
addons/hr_fleet/models/mail_activity_plan_template.py:68	HrEmployee	['car_ids']
addons/hr_recruitment/models/hr_applicant.py:602	HrApplicant	['talent_pools']
addons/hr_recruitment/models/hr_applicant.py:603	HrApplicant	['talent_pools']
addons/hr_recruitment/models/hr_talent_pool.py:112	HrTalentPool	['talents']
addons/hr_recruitment/wizard/talent_pool_add_applicants.py:71	HrApplicant	['categs']
addons/hr_skills/models/hr_employee.py:82	HrEmployee	['employee_skill_ids']
addons/hr_skills/models/hr_employee.py:96	HrEmployee	['employee_skill_ids']
addons/hr_skills/models/hr_employee.py:105	HrEmployee	['employee_skill_ids']
addons/hr_skills/models/hr_employee.py:137	HrEmployee	['versions']
addons/hr_skills/models/hr_employee_public.py:37	HrEmployee	['resume_line_ids']
addons/hr_skills/models/hr_employee_public.py:44	HrEmployee	['employee_skill_ids']
addons/hr_skills/models/hr_skill_level.py:109	HrSkillType	['skill_level_ids']
addons/hr_skills/models/hr_skill_type.py:141	HrSkillType	['skill_level_ids']
addons/hr_skills/models/resource_resource.py:26	ResourceResource	['hr_hremployee_resource_mixin_set']
addons/hr_skills/models/resource_resource.py:32	HrEmployee	['employee_skill_ids']
addons/hr_timesheet/models/hr_employee.py:52	HrEmployee	['timesheets']
addons/hr_timesheet/models/project_project.py:117	Project	['timesheets']
addons/hr_timesheet/models/project_task.py:98	ProjectTask	['timesheets']
addons/project_hr_skills/models/res_users.py:36	HrEmployee	['employee_skill_ids']
addons/purchase_requisition/models/purchase_requisition.py:453	PurchaseRequisitionLine	['supplier_info_ids']
addons/purchase_requisition/models/purchase_requisition.py:513	PurchaseRequisitionLine	['supplier_info_ids']
addons/purchase_requisition/models/purchase_requisition.py:743	PurchaseRequisitionLine	['supplier_info_ids']
addons/purchase_requisition/models/purchase_requisition.py:759	PurchaseRequisitionLine	['supplier_info_ids']
addons/stock/models/stock_move.py:724	ProductTemplate	['uom_ids']
addons/stock/models/stock_move.py:725	ProductTemplate	['seller_ids']
addons/website_sale/controllers/serializers.py:115	ProductCategory	['child_id']
```

Los tres de `timesheets` (`hr_timesheet`) los abrió la etapa 1a de analítica,
al hacer `BaseModel` a `account.analytic.line`; el resto, adopciones previas.

## Procedimiento

Por app, una prueba que ejercita el sitio por el ORM y falla hoy, y su
reescritura con la API del recordset de la fuente (`filtered`, `mapped`,
`sorted`, `len`, `search` sobre el comodelo, o el gestor del comodelo cuando
el sitio es una agregación SQL), citando en cada sitio la línea de la fuente
que porta. El dueño que atribuyó el subagente se verifica leyendo cada
sitio antes de tocarlo: es testimonio, no medida.

## Porción `hr_timesheet`

`has_timesheet` (`addons/hr_timesheet/models/hr_employee.py`,
≙ `_compute_has_timesheet`, `odoo19c: hr_timesheet/models/hr_employee.py:13-29`)
pasa a `bool(self.timesheets.filtered(lambda line: line.project))`;
`_effective_hours` (`project_project.py`, ≙ `_compute_remaining_hours`,
`:68-79`) y `effective_hours` (`project_task.py`, ≙
`_compute_effective_hours`, `:83-92`) suman `mapped('unit_amount')`. El
addon no tenía ninguna prueba; la nueva,
`tests/unit/hr_timesheet/test_timesheet_recordset_readers.py`, falla en los
tres antes del cambio con el `AttributeError` del recordset.
