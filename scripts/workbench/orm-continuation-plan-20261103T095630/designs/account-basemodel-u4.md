# Account U4 — los cinco modelos de informe adoptan `BaseModel`

Fecha: 2026-11-24T05:07:55. TASK-API-0397, unidad hija de `basemodel-adoption-0397`.
Partición: `outputs/account-basemodel-adoption-research.md`, unidad U4 (las
cinco clases de `account.report*`, todas sus relaciones internas).

Referencia (`odoo-tools@abe4040ec1`, Odoo 19 Community):
odoo19c: addons/account/models/account_report.py:44-47 — `account.report`,
`_order = 'sequence, id'`; odoo19c: addons/account/models/account_report.py:349-352
— `account.report.line`, `_order = 'sequence, id'`;
odoo19c: addons/account/models/account_report.py:579-582 —
`account.report.expression`, `_rec_name = 'report_line_name'`;
odoo19c: addons/account/models/account_report.py:932-935 —
`account.report.column`, `_order = 'sequence, id'`;
odoo19c: addons/account/models/account_report.py:947-951 —
`account.report.external.value`, `_check_company_auto = True`,
`_order = 'date, id'`.

## Qué cambia

1. Las cinco clases pasan de `(models.RecordLoaderMixin, models.Model)` a
   `models.BaseModel`.
2. `AccountReportExternalValue` declara `_check_company_auto = True`, que
   la fuente declara y este árbol no.
3. Pasan a recordset las relaciones internas (`root_report`/`variants`,
   `section_reports`/`section_main_reports`, `report`/`lines`,
   `parent`/`children`, `report_line`/`expressions`, `report`/`columns`,
   `target_report_expression`/`external_values`,
   `carryover_origin_report_line`/`carryover_external_values`). El único
   consumidor con API de gestor es `resolver_opcion`, que tomaba el primer
   informe principal con `.first()`: pasa a `[:1]` y a verdad.

4. `code` de la línea pasa a `null=True` sin `default=''`: la fuente
   guarda NULL cuando falta (odoo19c: addons/account/models/account_report.py:386)
   y `_code_uniq` (`unique (report_id, code)`,
   odoo19c: addons/account/models/account_report.py:398-401) no compara dos
   NULL. Con `''` un informe admitía una sola línea sin código; lo destapó la
   prueba de esta unidad al crear dos. La migración
   `account/0053_report_line_code_null` permite el NULL y pasa a NULL las
   filas que guardaban `''`.

Prueba: `tests/unit/account/test_account_report_basemodel.py`. Anulación,
restaurada con `cmp`: volver a `default=''` tumba sólo
`test_the_lines_of_a_report_are_a_recordset`.

## Citas de la fuente por archivo

- `addons/account/models/account_report.py`: odoo19c: addons/account/models/account_report.py:44-47,
  odoo19c: addons/account/models/account_report.py:349-352,
  odoo19c: addons/account/models/account_report.py:579-582,
  odoo19c: addons/account/models/account_report.py:932-935
  odoo19c: addons/account/models/account_report.py:947-951
  y odoo19c: addons/account/models/account_report.py:386-401.
- `addons/account/migrations/0053_report_line_code_null.py`: odoo19c: addons/account/models/account_report.py:386-401.

Pruebas: `tests/unit/account/test_account_report_basemodel.py`.

## Símbolos tocados por archivo

- `addons/account/models/account_report.py`: `AccountReport`, `AccountReportLine`, `AccountReportExpression`, `AccountReportColumn`, `AccountReportExternalValue`, `resolver_opcion`.

## Lo que este corte no cierra

Nada propio de la unidad.
