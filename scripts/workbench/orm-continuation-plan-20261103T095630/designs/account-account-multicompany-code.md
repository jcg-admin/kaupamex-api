# La cuenta contable es multiempresa y su código depende de la empresa

Fecha: 2026-11-24T10:46:48. TASK-API-0397. Precondición U0(b) de la
partición (`outputs/account-basemodel-adoption-research.md:28-31, 305`):
U6 (`account.account` sobre `BaseModel`) no puede declarar
`_order = 'code, placeholder_code'` mientras `placeholder_code` no exista,
y `placeholder_code` no se puede portar solo.

## Lo que declara la fuente (Odoo 19 Community)

- odoo19c: addons/account/models/account_account.py:23 — `_order = "code, placeholder_code"`.
- odoo19c: addons/account/models/account_account.py:39-41 — `code` calculado
  (`_compute_code`, `_search_code`, `_inverse_code`) sobre
  `code_store = fields.Char(company_dependent=True)`, y `placeholder_code`
  calculado con búsqueda propia.
- odoo19c: addons/account/models/account_account.py:130-186 — `_field_to_sql`:
  `code` es `code_store` leído con la empresa raíz activa;
  `placeholder_code` es `COALESCE(code_store->>raíz activa,
  code_store->>raíz de la primera empresa autorizada || ' (' || nombre || ')')`;
  `root_id` es `SUBSTRING(placeholder_code, 1, 2)`.
- odoo19c: addons/account/models/account_account.py:335-377 — los tres
  métodos de `code` y los dos de `placeholder_code`: el inverso escribe
  en la empresa raíz e invalida `code` para todas las empresas de esa raíz.
- odoo19c: addons/account/models/account_account.py:1079-1130 —
  `_ensure_code_is_unique`: código presente en cada raíz de `company_ids` y
  sin duplicados en empresas padre o hija. Sustituye a la restricción única
  `(company, code)` que este árbol declara en SQL.
- La cuenta no tiene `company_id`: sólo `company_ids` (Many2many a
  `res.company`).

## El estado heredado (medido 2026-11-24)

- `code = Char(max_length=64)` columna plana; `company` Many2one con
  `related_name='accounts'`; `UniqueConstraint(['company', 'code'])`;
  `Meta.ordering = ['code']`; `_check_company_domain` divergente declarado
  porque falta `company_ids` (`account_account.py:46-54`).
- El ORM ya porta `CompanyDependent` en jsonb `{company_id: valor}` con
  despachador para `Char` (`src/orm/fields_company_dependent.py:247, 485`);
  precedente en uso: `analytic_plan.default_applicability`
  (`addons/analytic/models/analytic_plan.py:199`). No hay todavía ningún
  `Char` dependiente de empresa declarado en un addon.
- Consumidores: 15 sitios `AccountAccount.objects` con `company`/`code`,
  14 `filter/get` por `company`/`code` sobre cuentas, 10 `order_by('code')`
  (uno es de `ResCompany`), 1 `account__code`/`account__company`; los dos
  archivos más cargados son `tests/unit/account/test_chart_template.py` y
  `addons/account/services.py`.

## Partición — tres unidades, cada una con su gate

**MC1 — `company_ids` y `code_store`, en paralelo a las columnas actuales.**
Se añaden `company_ids` (Many2many a `base.ResCompany`) y `code_store`
(`fields.Char(company_dependent=True)`). La migración copia `company` a
`company_ids` y escribe en `code_store` el código bajo la empresa raíz de
esa compañía. `code` y `company` siguen siendo columnas en MC1: `save`
mantiene `company_ids` y `code_store` al día, porque los ~30 consumidores
filtran y ordenan por ellas con el ORM de Django, que no filtra un campo no
almacenado (corregido 2026-11-24T11:20:49: la primera partición hacía `code`
calculado ya en MC1 y rompía esos sitios en el acto).
Pruebas: la migración llena las dos columnas nuevas; crear o cambiar el
código de una cuenta actualiza `code_store` bajo la raíz de su empresa; dos
empresas de la misma raíz leen el mismo `code_store`.

**MC2 — los consumidores dejan `company` y `code` como columnas.** Medido
el 2026-11-24 al abrirla: 13 sitios de producción y de prueba filtran u
ordenan cuentas por `company` o `code`, **89 altas** en 32 archivos pasan
`company=` a `AccountAccount.objects.create`/`get_or_create`, y 4 leen
`account.company`. Se divide en tres pasos, cada uno con su gate:

- **MC2a — lecturas.** Los filtros por `company` pasan a `company_ids`,
  `order_by('code')` queda donde la columna siga existiendo y el resto se
  lee por el orden del modelo. Las 4 lecturas de `account.company` pasan a
  `company_ids`.
- **MC2b — altas.** Las 89 altas declaran `company_ids` como la fuente
  (odoo19c: addons/account/models/account_account.py:97-99, `required=True`
  con la empresa activa por defecto), y `company` deja de exigirse.
- **MC2c — retirada.** `code` pasa a calculado con inverso y búsqueda,
  `_ensure_code_is_unique` sustituye a la restricción SQL, se retiran las
  columnas `code` y `company`, y `_check_company_domain` pasa al plural
  `check_companies_domain_parent_of` de la fuente (:25).

**MC3 — `placeholder_code` y `_order`.** `placeholder_code` con cómputo,
búsqueda y su expresión SQL, y `root_id` derivado de él con
`account_root_from_code`. `_order = 'code, placeholder_code'` deja de ser
nominal. Con MC3, U6 queda desbloqueada.

## Citas de la fuente por archivo

- `addons/account/models/account_account.py`: odoo19c: addons/account/models/account_account.py:23,
  odoo19c: addons/account/models/account_account.py:39-41,
  odoo19c: addons/account/models/account_account.py:130-186,
  odoo19c: addons/account/models/account_account.py:335-377 y
  odoo19c: addons/account/models/account_account.py:1079-1130.

## MC1 — símbolos tocados por archivo

- `addons/account/models/account_account.py`: `AccountAccount`, `save`, `_sync_code_store`.
- `addons/account/migrations/0055_account_company_ids_code_store.py`: `0055_account_company_ids_code_store`.

## MC1 — pruebas

`tests/unit/account/test_account_account_company_code_store.py`:
`test_the_account_belongs_to_its_company`,
`test_the_code_is_stored_under_the_root_company` y
`test_changing_the_code_rewrites_the_root_value`.

Anulación: sin `_sync_code_store` en `save` caen las dos últimas; la
primera depende sólo del alta en `company_ids`.

## MC2a — símbolos tocados por archivo

La fuente filtra estas búsquedas con `_check_company_domain(company)`, que
en la cuenta es `check_companies_domain_parent_of` sobre `company_ids`
(odoo19c: addons/account/demo/account_demo.py:669-675,
odoo19c: addons/account/models/account_analytic_distribution_model.py:53-57).
MC2a pasa el filtro de `company` a igualdad en `company_ids`, que da lo
mismo mientras `company_ids` replique `company`; el `parent_of` llega en
MC2c con el plural. Las dos lecturas de `account.company`
(`_get_closest_parent_account`, `account_merge_wizard`) quedan para MC2c,
porque la fuente las resuelve con la empresa activa y no con la columna.

- `addons/account/services.py`: `_require_account`.
- `addons/account/models/account_analytic_distribution_model.py`: `_compute_prefix_placeholder`.
- `addons/account/demo/account_demo.py`: `_get_demo_account`.

## MC2a — pruebas

`tests/unit/account/test_chart_template.py` filtra las cuentas cargadas por
`company_ids` en sus nueve consultas (`test_loads_the_four_families`, las
de sucursal y raíz, y las de plantilla). Anulación: sin el alta en
`company_ids` de `save` (MC1) caen esas consultas.

## Lo que este diseño no cierra

Cada unidad registra su fila en el plan al abrirse (`account-account-mc1-0397`,
`-mc2-0397`, `-mc3-0397`); U6 depende de la tercera. Los métodos de fusión
de cuentas (odoo19c: addons/account/models/account_account.py:1171-1250)
también leen `company_ids` y se revisan en MC2.
