# U6 — `account.account` adopta `BaseModel`, con `placeholder_code` (MC3)

Fecha: 2026-11-24T15:18:37. TASK-API-0397. Unidad U6 de la partición
(`outputs/account-basemodel-adoption-research.md:311`) ejecutada junto con
MC3 de `designs/account-account-multicompany-code.md`, porque la expresión
SQL de `placeholder_code` sólo se ejerce sobre `BaseModel`
(`FieldSqlMixin._field_to_sql`, `src/orm/models.py:2699`;
`_order_field_to_sql`, `:4551`).

## Referencia (Odoo 19 Community)

- odoo19c: addons/account/models/account_account.py:20-25 — `_name`,
  `_inherit`, `_description`, `_order = "code, placeholder_code"`,
  `_check_company_auto`, `_check_company_domain`.
- odoo19c: addons/account/models/account_account.py:41 — `placeholder_code`
  calculado con búsqueda.
- odoo19c: addons/account/models/account_account.py:130-186 —
  `_field_to_sql` de `placeholder_code` (COALESCE del código de la raíz
  activa y del de la primera empresa autorizada con su nombre).
- odoo19c: addons/account/models/account_account.py:357-377 —
  `_compute_placeholder_code` y `_search_placeholder_code`.

## Censo de lo que rompe (2026-11-24, subagente de lectura)

Los dueños de las 12 relaciones hacia la cuenta ya son `BaseModel`; ningún
sitio usa la API del gestor sobre los 7 reversos. Rompen:

- `tags` usado como gestor: `account_account.py:318, 322`
  (`exists()`, `set()`), `l10n_mx/models/account_account.py:90, 95`
  (`filter().exists()`, `add()`), `tests/unit/account/test_chart_template.py`
  (6 líneas), `tests/unit/orm/test_compute_writes_m2m.py` (9 líneas).
- `is not None` sobre una relación: `test_chart_template.py:643`.
- `.delete()`: `wizard/account_merge_wizard.py:335`,
  `tests/unit/orm/test_restrict_ondelete_non_company.py:113`; pasan a
  `unlink()`.
- `QuerySet.update`: `tests/unit/orm/test_compute_writes_m2m.py:341`; se
  conserva (es el gestor `objects`, que sigue existiendo).
- Por revisar al implementar: ~8 variables locales `account is None` cuyo
  valor puede venir ahora de una relación (`chart_template.py:902, 911,
  1047, 1107`, `services.py:37`, `account_fiscal_position.py:214`,
  `account_analytic_plan.py:174`, `account_demo.py:925`).

## Qué cambia

1. `AccountAccount(models.BaseModel)`; `Meta.ordering` se conserva para el
   gestor de Django y `_order` deja de ser nominal.
2. `placeholder_code = fields.Char(compute=…, search=…, store=False)` con
   `_compute_placeholder_code`, `_search_placeholder_code` y la rama de
   `_field_to_sql`. Mientras `code` siga siendo columna (hasta MC2c), la
   expresión lee `code_store` de la raíz activa como la fuente y cae a la
   primera empresa autorizada con su nombre.
3. Los sitios del censo pasan a la forma de recordset.

## Pruebas

`tests/unit/account/test_account_account_basemodel.py`:
`test_the_account_is_a_basemodel`,
`test_the_placeholder_is_the_code_in_the_active_company`,
`test_the_placeholder_names_another_company`,
`test_the_order_uses_the_placeholder`.

## Símbolos tocados por archivo

- `addons/account/models/account_account.py`: `AccountAccount`, `save`, `_compute_account_tags`, `_compute_placeholder_code`, `_search_placeholder_code`, `_field_to_sql`.
- `addons/l10n_mx/models/account_account.py`: la función del gancho que etiqueta las cuentas.
- `addons/account/wizard/account_merge_wizard.py`: el método que borra las cuentas fusionadas.

## Lo que este diseño no cierra

MC2b y MC2c (`designs/account-account-multicompany-code.md`) siguen a esta
unidad.
