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

## Lo que destapó la adopción (2026-11-24)

Sobre `BaseModel` el ORM invoca los cómputos sobre el lote entero. Los tres
cómputos del modelo estaban escritos para un registro y reventaban con
`Expected singleton`. Pasan a la forma de la fuente, que filtra el lote y
asigna por registro (odoo19c: addons/account/models/account_account.py:603-611).
`_get_closest_parent_account` lee el Many2many de la cuenta padre de la
tabla y no del descriptor, porque leerlo lo recomputaría sobre el lote que
se está calculando. El cargador del plan escribía los Many2many con
`getattr(record, name).set(...)`, que en un `BaseModel` es un recordset;
pasa a `related_manager`, que sirve para los dos casos.

## Símbolos tocados por archivo

- `addons/account/models/account_account.py`: `AccountAccount`, `save`, `_compute_internal_group`, `_compute_account_type`, `_compute_account_tags`, `_get_closest_parent_account`, `_compute_placeholder_code`, `_search_placeholder_code`, `_field_to_sql`, `_authorized_company_ids`, `_root_company_id`.
- `addons/account/models/chart_template.py`: `load_model_data`, `load_child_lines`.
- `addons/l10n_mx/models/account_account.py`: `_apply_l10n_mx_balance_tag`.
- `addons/account/wizard/account_merge_wizard.py`: `_action_merge`.
- `addons/account/models/product.py`: `_get_category_account` — subía el árbol
  comparando con `None`; con la cuenta como recordset una categoría sin
  cuenta devuelve el vacío y el bucle paraba en la primera. Pasa a la forma
  de la fuente: `if account:` y el recordset vacío al final
  (odoo19c: addons/account/models/product.py:80-92). Lo destapó el gate.

## Auxiliares de `placeholder_code`

- `_authorized_company_ids` es `self.env.user._get_company_ids()` de la
  fuente (odoo19c: addons/account/models/account_account.py:160, 362):
  las empresas del usuario, no las activas del contexto. Sin usuario no
  acota.
- `_root_company_id` es la raíz de una empresa, la clave con que
  `code_store` guarda el código (odoo19c: addons/account/models/account_account.py:134, 169-170).

La prueba fija un usuario contable con acceso a las dos empresas: el
usuario de sistema de este árbol no tiene ninguna, y con él la fuente no
autoriza ninguna empresa.

## Lo que este diseño no cierra

MC2b y MC2c (`designs/account-account-multicompany-code.md`) siguen a esta
unidad.
