# La cabecera de `account.analytic.line` y de su mixin

Unidad `analytic-model-headers-0121` (TASK-API-0121), que dependía de
`account-model-headers-0121` (aceptada en `ca5481c2`).

## Contrato medido en la referencia

| Modelo | Fuente | Cabecera |
|---|---|---|
| `analytic.plan.fields.mixin` | `odoo19c: addons/analytic/models/analytic_line.py:11-14` | `AbstractModel`, `_name`, `_description = 'Analytic Plan Fields'` |
| `account.analytic.line` | `odoo19c: addons/analytic/models/analytic_line.py:163-168` | `_name`, `_inherit = ['analytic.plan.fields.mixin']`, `_description = 'Analytic Line'`, `_order = 'date desc, id desc'`, `_check_company_auto = True` |

La segunda obligación de la unidad, `AccountInvoiceReport._name`
(`odoo19c: addons/account/report/account_invoice_report.py:12`), ya está
declarada en `addons/account/report/account_invoice_report.py:164-168` con
toda su cabecera: no se toca.

## Cambios

1. `AnalyticPlanFieldsMixin` declara `_name`, `_description` y
   `_abstract = True` (es un `AbstractModel` en la fuente; su `Meta` ya es
   abstracto).
2. `AccountAnalyticLine` declara los cinco atributos verbatim.
   `_check_company_auto` entra entero: `_check_company` resuelve la empresa
   del registro por `COMPANY_FIELD_NAMES = ('company', 'company_id')`
   (`src/orm/models.py:1511`), así que la FK `company` de este puerto basta.
   Hoy ningún campo relacional del modelo declara `check_company=True`, de
   modo que la verificación no tiene campos que recorrer.
3. Migración `analytic/0013_model_headers`: con `_name` el modelo es de
   acceso registrado, como en la fuente (`LOG_ACCESS_COLUMNS`,
   `odoo19c: odoo/orm/models.py:283-296`), y la inyección le añade
   `create_uid`, `create_date`, `write_uid` y `write_date`; sin la migración
   el registro rehúsa cargar (*«their migration is missing»*). Misma forma
   que `account/0038_model_headers`.
4. `apply_account_extensions` (`addons/account/models/account_analytic_line.py`)
   anota con `note_model_extended_by('account', AccountAnalyticLine)` que
   `account` extiende el modelo, como ya hace `account/models/partner.py:190`
   con `res.partner`. En la fuente todo módulo que extiende un modelo recibe
   su XML-ID (`odoo19c: odoo/addons/base/models/ir_model.py:462-475`), y la
   fila de `purchase` nombra `account.model_account_analytic_line`; el
   `add_to_class` con que `account` cuelga sus campos no lo anotaba.
5. `purchase/security/ir.model.access.csv`: vuelve la fila de la fuente
   `access_account_analytic_line` (`:28`), en su posición; el manifiesto deja
   de declararla omitida y `test_purchase_security_data.py` espera 28 filas.

## Fuera de esta unidad, con su sucesor

- `check_company=True` en los relacionales que la fuente lo declara
  (`account_id`, `company_id`, `partner_id`, …) y los nombres de FK en forma
  A del apunte (`account`, `partner`, `company`, `product_uom`) —
  `analytic-fk-names-0121`.

## Pruebas

`tests/unit/analytic/test_analytic_model_headers.py`: las dos cabeceras
verbatim; las cuatro columnas de acceso registrado; el XML-ID de `account`
para el modelo; la fila de `purchase` cargada; y la anotación de que
`account` extiende el modelo. Control de anulación: sin la llamada a
`note_model_extended_by` cae sólo la prueba de la anotación — las del XML-ID
y la fila siguen verdes con `--reuse-db`, porque leen el estado de una carga
anterior, y por eso la prueba del mecanismo existe.
