# Account U2 — `account.group` y `account.account.tag` adoptan `BaseModel`

Fecha: 2026-11-24T03:00:21. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/account-basemodel-adoption-research.md`, unidad U2.

Referencia (`odoo-tools@abe4040ec1`, Odoo 19 Community):
odoo19c: addons/account/models/account_account.py:1497-1502 —
`_name = 'account.group'`, `_description = 'Account Group'`,
`_order = 'code_prefix_start'`, `_check_company_auto = True`,
`_check_company_domain = models.check_company_domain_parent_of`;
odoo19c: addons/account/models/account_account_tag.py:7-9 —
`_name = 'account.account.tag'`, `_description = 'Account Tag'`, y su
guarda `_unlink_except_master_tags` con `@api.ondelete(at_uninstall=False)`
(odoo19c: addons/account/models/account_account_tag.py:110-120).

## Qué cambia

1. Las dos clases pasan de `(models.RecordLoaderMixin, models.Model)` a
   `models.BaseModel`.
2. `AccountGroup` declara `_check_company_auto` y `_check_company_domain`
   (`classmethod(models.check_company_domain_parent_of)`, la forma que ya
   usan `account.account` y `account.journal` en este árbol).
3. El `delete` de `AccountAccountTag` pasa a `_unlink_except_master_tags`
   con `@api.ondelete(at_uninstall=False)`, que `BaseModel.unlink` ejecuta;
   la guarda recorre el recordset (`master.pk in self.ids`), como la fuente
   (`master_tag in self`). Las dos pruebas que borraban con `delete()`
   pasan a `unlink()`.
4. Cambian de tipo `parent`/`children` del grupo y el reverso
   `product_templates` de la etiqueta; nadie fuera de los modelos los lee
   con API de gestor.

Prueba: `tests/unit/account/test_account_group_and_tag_basemodel.py` y
`tests/unit/account/test_chart_template.py`.

## Citas de la fuente por archivo

- `addons/account/models/account_group.py`: odoo19c: addons/account/models/account_account.py:1497-1502.
- `addons/account/models/account_account_tag.py`: odoo19c: addons/account/models/account_account_tag.py:7-9
  y odoo19c: addons/account/models/account_account_tag.py:110-120.

Pruebas: `tests/unit/account/test_account_group_and_tag_basemodel.py` y
`tests/unit/account/test_chart_template.py`.

## Símbolos tocados por archivo

- `addons/account/models/account_group.py`: `AccountGroup`.
- `addons/account/models/account_account_tag.py`: `AccountAccountTag`, `_unlink_except_master_tags`.

## Lo que este corte no cierra

Nada propio de la unidad.
