# analytic-cluster-0397 — `account.analytic.account` y `account.analytic.line`

Unidades hijas de `basemodel-adoption-0397`, grupo `analytic` (las dos clases
de la app con `_name` fuera de `BaseModel`, medido con `apps.get_models()`).
Medición hecha con un subagente de lectura (2026-11-21) y comprobada en sus
citas de línea con `grep -n` sobre la referencia.

## Referencia y estado

- `odoo19c: addons/analytic/models/analytic_account.py` (243 líneas, 10
  `def`): el puerto tiene la cabecera idéntica (`_order`,
  `_check_company_auto`, `_check_company_domain`, `_rec_names_search`), pero
  `root_plan_id` (`:44`), `color` (`:50`), `currency_id` (`:90`) y
  `balance`/`debit`/`credit` (`:77-88`) son propiedades y no campos;
  `line_ids` (`:55`) no está declarado; `company_id` (`:61`) no tiene valor
  por defecto y `partner_id` (`:67`) no tiene `check_company`. Faltan
  `copy_data` (`:114`), `web_read` (`:122`), `_read_group_select` (`:128`),
  `_read_group_postprocess_aggregate` (`:142`),
  `_compute_debit_credit_balance` (`:163`),
  `_update_accounts_in_analytic_lines` (`:205`) y `write` (`:237`);
  `_check_company_consistency` (`:96`) vive como `clean`.
- `odoo19c: addons/analytic/models/analytic_line.py` (274 líneas): el mixin
  `analytic.plan.fields.mixin` (`:11`) no tiene `auto_account_id` (`:26`) ni
  sus cómputos, ni `_get_plan_fnames` (`:57`) … `_patch_view` (`:125`); la
  línea no declara `required` en `name`/`date`/`amount`, `currency_id`
  (`:211`) y `analytic_precision` (`:232`) son propiedades, y faltan
  `analytic_distribution` (`:227`) con su cómputo e inverso (`:237`, `:241`)
  y `_split_amount_fname` (`:269`).

## Dependencia medida: las columnas por plan

`auto_account_id` y `analytic_distribution` leen y escriben las columnas que
cada plan añade al modelo (`plan._column_name()`); el puerto no las crea
(docstring de `addons/analytic/models/analytic_line.py:15-24`). Es la misma
pieza que `account.analytic.plan` necesita, y se trata como etapa propia.

## Consumidores

Extensiones por `_add_if_absent`/`extend_model`/`chain_method` en `account`,
`sale`, `hr_timesheet` y `sale_timesheet`; lecturas `.objects.filter` en
`sale_timesheet` y en `analytic_mixin.py`; propiedades colgadas
(`invoice_count`, `vendor_bill_count`, `job_title`). Ninguna llamada de
producción a `objects.create` ni `annotate` sobre estos modelos.

## Etapas, en orden de dependencia

1. `BaseModel` y paridad de campos de cuenta y línea (cabeceras, valores por
   defecto, `required`, `check_company`, `root_plan_id` y `currency_id`
   almacenados, `color`, `analytic_precision`, `balance`/`debit`/`credit`
   con `_compute_debit_credit_balance`, `_compute_display_name`,
   `_check_company_consistency` y `_check_account_id` como restricciones),
   con las propiedades de los consumidores verificadas.
2. Columnas por plan: `auto_account_id`, `line_ids`, `analytic_distribution`
   y los métodos del mixin que las recorren.
3. `copy_data`, `write`, `_update_accounts_in_analytic_lines` y el
   agrupado (`_read_group_select`, `_read_group_postprocess_aggregate`).
4. Vista: `default_get`, `fields_get`, `_get_view`, `_patch_view`,
   `web_read`.

## La etapa 1 se parte en dos

La paridad de campos exige los nombres de la fuente en las FK
(`plan_id`, `company_id`, `partner_id`, `account_id` de
`odoo19c: addons/analytic/models/analytic_account.py:38-67` y
`analytic_line.py:16`), y el puerto los declara como `plan`, `company`,
`partner` y `account`, con muchos consumidores. Renombrar y adoptar
`BaseModel` a la vez mezcla dos riesgos, así que:

- **1a**: `AccountAnalyticAccount` y `AccountAnalyticLine` heredan de
  `models.BaseModel` delante de sus mixins, como el resto del programa
  (`odoo19c: odoo/orm/models.py:334`, `:7046`, `:7049`), y `analytic` sale de
  las apps pendientes. Se verifican los enganches de los consumidores:
  `chain_method` sobre `save`/`clean`
  (`addons/account/models/account_analytic_line.py`), el receptor
  `pre_save` de `hr_timesheet` y las propiedades colgadas.
- **1b**: los nombres de la fuente y la paridad de campos que el resto de
  esta etapa enumera.

Prueba de 1a: `tests/unit/analytic/test_analytic_basemodel.py`, con
`tests/unit/orm/test_basemodel_reach.py` y las pruebas de `analytic`,
`account` y `sale_timesheet` que tocan los dos modelos.

## Adenda de 1a: `_check_company_auto` estaba declarado y no tenía receptor

Medido al ejecutar la prueba de 1a: el alta por el ORM de
`AccountAnalyticAccount` muere con `AttributeError: ... no attribute
'_check_company'`. Las dos clases declaran `_check_company_auto = True`
(`odoo19c: addons/analytic/models/analytic_account.py:16`,
`analytic_line.py:168`), y `BaseModel._create` lo honra llamando a
`_check_company` (`odoo19c: odoo/orm/models.py:4009`). En el puerto ese
método lo aporta `models.CheckCompanyMixin`, que los demás modelos reciben
por `TimeStampedModel`; las dos clases analíticas no usan esa base, así que
el atributo era letra muerta desde antes de esta etapa.

Por eso 1a añade `models.CheckCompanyMixin` detrás de `models.BaseModel` en
`AccountAnalyticAccount` y `AccountAnalyticLine`. No cambia conducta hoy:
`_check_company` recorre los campos con `check_company=True`
(`analytic_line.py:21`, `:196`; `analytic_account.py:73`), y ninguno lo
declara todavía; declararlos es paridad de campos, etapa 1b. Tampoco el
default de `company_id` (`self.env.company`): la prueba de 1a pasa la
empresa explícita.

El control de anulación de 1a retira el mixin de cada clase y exige que caiga
`test_an_account_and_a_line_go_through_the_orm`, en
`tests/unit/analytic/test_analytic_basemodel.py`.

## 1b, primera unidad: `plan` de la cuenta pasa a `plan_id` (forma C)

La fuente declara `plan_id = fields.Many2one('account.analytic.plan',
required=True, index=True)` (`odoo19c: addons/analytic/models/analytic_account.py:38`)
y su inverso `account_ids = fields.One2many('account.analytic.account',
'plan_id')` (`odoo19c: addons/analytic/models/analytic_plan.py:58`). El puerto
los declara `plan` y `related_name='accounts'`.

Como en los precedentes de la forma C (`f61e2206`, `96e17d36`), la unidad es
una FK:

- `AccountAnalyticAccount.plan` se renombra `plan_id` con
  `db_column='plan_id'`: la columna no cambia y la migración es un
  `RenameField` sin SQL de datos. El inverso pasa a `account_ids`.
- Lectores medidos por receptor (`git grep` de `.plan`, `plan=`, `plan__`,
  `select_related('plan')` y `.accounts` sobre `addons/`, `src/` y `tests/`):
  `analytic_account.py` (`Meta.ordering`, `root_plan` y `color`),
  `analytic_distribution_model.py:124`, `analytic_mixin.py:331-354`,
  `analytic_plan.py:226` (`account_count`), y los altas con `plan=` en
  `tests/unit/analytic/` y `tests/unit/account/`.
- La línea de `scripts/fk_naming_baseline.txt` de esta FK sale.

El riesgo de la forma C es semántico, no de esquema: con `plan_id`
declarado, `account.plan_id` deja de ser el entero y pasa a ser el registro.
Se buscó `plan_id` leído como entero sobre una cuenta: el único uso es la
cadena de `_order`, que nombra la columna. La red es la suite entera (F2).

Prueba: `tests/unit/analytic/test_analytic_account_plan_id.py` —el símbolo,
la columna, el inverso `account_ids` y `account_count` sobre él—, con las
pruebas de `analytic`, `account` y `sale_timesheet` que crean cuentas.

### Adenda de la unidad `plan_id`: el orden por un comodelo de Django

Medido al ejecutar la prueba: con `plan_id` declarado, la búsqueda ordena por
`_order = 'plan_id, name asc'` (`odoo19c: addons/analytic/models/analytic_account.py:15`),
y `_order_field_to_sql` desciende al `_order` del comodelo. `account.analytic.plan`
sigue siendo un modelo de Django sin `_order`, y la búsqueda muere con
`AttributeError`. En la fuente todo modelo tiene `_order`, con default `'id'`
(`odoo19c: odoo/orm/models.py:434`); por eso `_order_field_to_sql`
(`src/orm/models.py`) toma `'id'` cuando el comodelo de Django no declara el
suyo. Prueba: `test_the_default_order_follows_the_plan_by_id`, con nombres
de plan cuyo orden alfabético contradice el de `id`, en
`tests/unit/analytic/test_analytic_account_plan_id.py`.

**El plan escapó del programa de adopción.** El censo de
`basemodel-adoption-0397` cuenta los modelos con `_name`, y el puerto de
`account.analytic.plan` no declara ninguno de los atributos de clase de la
fuente (`_name`, `_description`, `_parent_store`, `_rec_name`, `_order`,
`odoo19c: addons/analytic/models/analytic_plan.py:14-18`). Declararlos no se
puede en esta unidad: `_rec_name = 'complete_name'` exige que
`complete_name` sea campo (es propiedad) y `_parent_store` exige el padre
como `parent_id` (es `parent`). Se intentó y la carga de módulos falló con
`Dependency field 'complete_name' not found`. Sucesor:
`analytic-plan-basemodel-0397` —cabecera, `BaseModel`, `parent_id`,
`complete_name`, `root_id` y los campos de la fuente del plan—, que precede
a la etapa 2 (columnas por plan).

Símbolos que la unidad `plan_id` cambia, para el gate de flujo de
referencia: `AccountAnalyticAccount.plan_id` y su `Meta.ordering`, las
propiedades `root_plan` y `color` (`analytic_account.py`);
`AccountAnalyticDistributionModel._get_distribution`
(`analytic_distribution_model.py`), que lee el plan raíz de cada cuenta;
`AnalyticMixin._modifiying_distribution_values` (`analytic_mixin.py`), que
hace lo mismo en las dos pasadas; `AccountAnalyticPlan.account_count`
(`analytic_plan.py`) sobre `account_ids`; la migración
`0014_account_plan_id` (`AlterField` + `RenameField` + `AlterModelOptions`,
sin SQL); y `_order_field_to_sql` (`src/orm/models.py`). Ninguno cambia de
conducta salvo `_order_field_to_sql`; los demás leen el mismo valor por su
nombre de la fuente. Prueba: `tests/unit/analytic/test_analytic_account_plan_id.py`.
