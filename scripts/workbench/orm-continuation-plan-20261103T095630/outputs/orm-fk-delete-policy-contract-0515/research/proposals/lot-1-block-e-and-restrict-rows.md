# Lote 1 — bloque E y filas `restrict` pendientes (TASK-API-0515)

- **Unidad:** `orm-fk-delete-policy-contract-0515`
- **Revisión base:** `286faed0` (rama `feature/vm-x2hokp-orm-root`)
- **Fecha UTC:** 2026-11-17T22:25:00Z (`date -u`)
- **Estado:** COMPLETO (sólo lectura; no se ejecutó pytest, `manage.py`, migraciones ni nada contra PostgreSQL)
- **Cobertura:** 27 de 27 filas con evidencia de fuente y de nuestro árbol. Con parte UNVERIFIED: 5 de 27 (ver §7).
- Referencia: `odoo19c:` = `/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0`, `odoo-tools@abe4040ec1` (`git rev-parse --short=10 HEAD`; `git status --porcelain` vacío).
- Insumos: `lot-0-remaining-xfail-rows.md`, `designs/restrict-ondelete-non-company.md`, `designs/set-null-ondelete-block-d.md` (línea 22 asigna el `unlink` de proyecto al «bloque E»), `designs/restrict-ondelete-payment-method-line.md` (precedente de adopción de `BaseModel`).

## 0. Resumen ejecutable

| # | Fila(s) | Política | Qué hace falta |
|---|---|---|---|
| 1 | `hr.HrVersion.employee` | `SET_NULL` | **Ningún `unlink` nuevo.** Borrar un empleado deja las versiones huérfanas (`employee_id` NULL) en la fuente; hoy las borramos. Sólo cambia la política. `_unlink_except_last_version` es otra unidad (#525). |
| 2 | `project.ProjectTask.project` | `SET_NULL` | `Project` pasa a `BaseModel` y gana `unlink` que borra **todas** sus tareas (activas o no) antes de `super()`. Sin eso `SET_NULL` convierte en huérfanas (tareas «privadas») las que la fuente borra. |
| 3 | `account.AccountPartialReconcile.debit_move`, `credit_move` | `PROTECT` | `remove_move_reconcile` + `AccountMoveLine.unlink` **y** `AccountMove.unlink` (la fuente también llama `line_ids.remove_move_reconcile()` allí); los parciales ya tienen un `delete_and_update_matching` que se reutiliza. |
| 4 | `stock.StockRule.picking_type` | `PROTECT` | Sólo la política. `stock.picking.type` no tiene `unlink` ni `@api.ondelete` en la fuente ni en ninguna de sus 10 extensiones de Community. |
| 5 | 22 filas hacia `res.company` (21 `PROTECT` + la de bank statement line) | `PROTECT` | Sólo la política. La de `AccountBankStatementLine.company` es `PROTECT` (la fuente la declara `set null` físico sobre columna NOT NULL, que **rehúsa** el borrado). Radio: **7 archivos / 7 sitios** borran empresas; ninguno crea hijos de las 22 filas (estático). |

## 1. `hr.HrVersion.employee` [set null]

**Fuente.**
- `odoo19c: addons/hr/models/hr_version.py:54-59`: `employee_id = fields.Many2one('hr.employee', ..., index=True)`; sin `ondelete`, no `required` → `set null` por defecto (`odoo19c: odoo/orm/fields_relational.py:274-282`: `'restrict' if self.required else 'set null'`).
- `odoo19c: addons/hr/models/hr_employee.py:43` `_inherits = {'hr.version': 'version_id'}`; `:46-53` `version_id` es `compute`, `store=False`, `required=True`, `ondelete='cascade'`. **No es columna**: `store=False` ⇒ no hay FK física empleado→versión. La única FK física es `hr_version.employee_id`.
- `odoo19c: addons/hr/models/hr_employee.py:66-71` `version_ids = One2many('hr.version', 'employee_id', required=True)` (un One2many no tiene columna).
- `odoo19c: addons/hr/models/hr_employee.py:1473-1476` `unlink`: `resources = self.mapped('resource_id'); super().unlink(); return resources.unlink()` — sólo retira el `resource`.
- `odoo19c: odoo/orm/models.py:4194-4333` `BaseModel.unlink`: ejecuta `_ondelete_methods`, `DELETE FROM <tabla>`, limpia `ir.model.data`/`ir.attachment`/defaults; el recorrido de `_inherits` (`odoo19c: odoo/orm/models.py:4693,5201,5425`) vive en `create`/`load`/`copy`, **ninguna** de esas apariciones cae dentro de `unlink` (`awk 'NR>=4194 && NR<=4340 && /_inherits/' | wc -l` → 0). Es decir, **`_inherits` no borra el padre al borrar el hijo**.
- `odoo19c: addons/hr/models/hr_version.py:294-300` `@api.ondelete(at_uninstall=False) _unlink_except_last_version`: borrar versiones que sean **todas** las de un empleado levanta `ValidationError`.

**Conclusión de fuente.**
- Borrar un empleado: se borra la fila `hr_employee`; en `hr_version` la FK `employee_id` pasa a NULL; **las versiones sobreviven huérfanas**. Se borra el `resource`.
- Borrar una versión: permitido salvo que sea la última del empleado (guarda `ondelete`). Como `hr.employee.version_id` no es columna, no hay efecto sobre el empleado en la fila; su `version_id` se recalcula desde `current_version_id`.

**Nuestro árbol.**
- `addons/hr/models/hr_version.py:170-182`: `employee = Many2one('hr.HrEmployee', on_delete=models.CASCADE, null=True, related_name='versions')` — **destruye** las versiones al borrar el empleado (la fuente las conserva).
- `addons/hr/models/hr_employee.py:378-388`: `version = Many2one(HrVersion, on_delete=models.SET_NULL, null=True, related_name='+')`: FK real que sustituye a `_inherits`/`version_id` (divergencia declarada: «Aquí es una FK real (Django no tiene delegación de campos)»). Borrar una versión pone `version` a NULL en el empleado; coherente con el recálculo de la fuente. No requiere cambio.
- `HrVersion` y `HrEmployee` ya derivan de `models.BaseModel` (`hr_version.py:83`, `hr_employee.py:343`): hay infraestructura `unlink`/`@api.ondelete` (`src/orm/models.py:6129-6184` `_run_ondelete_checks`/`Collector.collect`; `:8965` `BaseModel.unlink`).
- `src/orm/inherits.py` implementa lectura/escritura delegadas; el docstring del módulo dice que el alta del padre va en `BaseModel.create` y no menciona borrado: no hay ningún camino «borrar hijo ⇒ borrar padre» que copiar, y no debe haberlo.
- `HrEmployee` **no** declara `unlink` (`grep "def delete\|def unlink" addons/hr/models/hr_employee.py` → sin resultados; el docstring `:296-298` lo lista en la familia (e) «mecánica `_inherits` de alta/baja»). El `unlink` de la fuente sólo borra el `resource`; es porte aparte (no cambia la política de la fila).
- Consumidor de borrado: `addons/hr_timesheet/wizard/hr_employee_delete_wizard.py:86` (`employee.delete()`, ≙ `odoo19c: addons/hr_timesheet/wizard/hr_employee_delete_wizard.py:45-47` `employee_ids.unlink()`): con `SET_NULL` conserva las versiones, como la fuente. Tests que borran empleados: `tests/unit/orm/test_restrict_ondelete_non_company.py:84` (espera `ProtectedError` por el mapa de `sale_timesheet`, independiente de versiones). `grep -rn "versions"` no halla consumidores que dependan de que el borrado del empleado arrastre sus versiones.

**Política y `unlink` requeridos.** `HrVersion.employee` → `on_delete=models.SET_NULL` (`null=True` ya existe; columna ya nullable). **Ningún `unlink` nuevo es necesario** para igualar la conducta de la fuente. Pendiente aparte, no de esta fila: `_unlink_except_last_version` (`@api.ondelete`, `hr_version.py:115` del docstring lo lista como #525). Nota: con `SET_NULL` y esa guarda ausente, `Collector` de Django no la ejecutaría de todos modos para filas borradas en cascada.

Riesgo anotado: `grouped('employee_id')` de la guarda de la fuente (`:296`) trata el caso `employee_id` vacío; la guarda portada debe tolerar versiones huérfanas.

## 2. `project.ProjectTask.project` [set null]

**Fuente.** `odoo19c: addons/project/models/project_task.py:192` `project_id = Many2one('project.project', compute='_compute_project_id', store=True, precompute=True, recursive=True, readonly=False, index=True, ...)`: sin `ondelete`, no required → `set null`.

`unlink` completo (`odoo19c: addons/project/models/project_project.py:704-717`):
```
704    def unlink(self):
705        # Delete the embedded action configs related to the deleted projects
706        self.env['res.users.settings.embedded.action'].sudo().search(
707            domain=[('res_id', 'in', self.ids), ('res_model', '=', self._name)],
708        ).unlink()
709        # Delete the empty related analytic account
710        analytic_accounts_to_delete = self.env['account.analytic.account']
711        for project in self:
712            if project.account_id and not project.account_id.line_ids:
713                analytic_accounts_to_delete |= project.account_id
714        self.with_context(active_test=False).tasks.unlink()
715        result = super().unlink()
716        analytic_accounts_to_delete.unlink()
717        return result
```
y, a continuación, `:719-723` `@api.ondelete(at_uninstall=False) _check_project_group_at_removal` (desactiva grupos si se borra el último proyecto con `allow_task_dependencies`/`allow_milestones`/`allow_recurring_tasks`).

Qué hace, por paso:
1. Borra `res.users.settings.embedded.action` con `res_model='project.project'` y `res_id in ids` (`:706-708`).
2. Recoge las cuentas analíticas del proyecto **sin líneas** (`:710-713`).
3. **Borra todas las tareas, incluidas las archivadas** (`with_context(active_test=False).tasks.unlink()`, `:714`). Cada tarea pasa por `project.task.unlink` (`odoo19c: addons/project/models/project_task.py:1388-1394`): añade subtareas (`_get_all_subtasks`), y borra la `recurrence` si la tarea es la última de su recurrencia.
4. `super().unlink()` (`:715`), luego borra las cuentas analíticas vacías (`:716`).
5. `@api.ondelete` de grupos (`:719-723`), antes de todo lo anterior (Odoo corre las `_ondelete_methods` al inicio de `BaseModel.unlink`, `odoo/orm/models.py:4205-4208`).

**Nuestro árbol** (`addons/project/models/project_project.py`, 64 líneas; `project_task.py`, 99 líneas):
- `Project(TimeStampedModel)` — **no** es `BaseModel`; sin `unlink`/`delete`. Cabecera: «Se omite la analítica contable de Odoo» (sin `account_id`).
- `ProjectTask.project`: `on_delete=models.CASCADE, null=True` (`project_task.py:31-36`), `related_name='tasks'`. Hoy el CASCADE de Django reproduce el paso 3 **sin** subtareas ni recurrencia (no existen en nuestro port: sin `parent`/`recurrence`).
- Paso 1 (embedded actions): **MISSING** en `Project`. Existe el modelo `addons/web/models/res_users_settings_embedded_action.py:72-106` con `res_model`/`res_id`, así que el paso es portable. (No hay nada que lo borre hoy: queda huérfano al borrar un proyecto; es un `Char`+`Integer`, sin FK.)
- Paso 2 y 4 (analítica): **BLOCKED** — `Project.account_id` no existe (`project_project.py:8-10`; `sale_timesheet` lo declara BLOQUEADO por lo mismo, `addons/sale_timesheet/models/project_project.py:147`).
- Paso 5: **MISSING**; `_check_project_group_with_field`/`allow_*` no existen en nuestro árbol (`grep` vacío).
- Subtareas/recurrencia del paso 3: no aplica (campos ausentes por Cláusula 5 declarada en la cabecera de `project_task.py`).

**Mínimo fiel.** (a) `ProjectTask.project` → `SET_NULL`; (b) `Project` a `models.BaseModel, TimeStampedModel` (precedente: `designs/restrict-ondelete-payment-method-line.md` §6, «adopción de `BaseModel` (clase A)»; esquema no cambia); (c) `Project.unlink`: borrar embedded actions por `res_model/res_id`, luego `self.tasks.all()` (el related manager de Django no filtra `active`, equivale a `active_test=False`), luego `super().unlink()`. Declarar como diferidos: analítica (BLOQUEADO por `account_id`), `_check_project_group_at_removal`, subtareas y recurrencia.
Contrato esperado: `unlink` del proyecto borra sus tareas; un `delete()` crudo del proyecto las deja con `project` NULL (≙ SQL directo de la fuente). Efecto colateral: `test_a_project_with_employee_rates_is_protected` (`tests/unit/orm/test_restrict_ondelete_non_company.py:72-78`) no cambia (usa `PROTECT` de `sale_timesheet`).

## 3. `account.AccountPartialReconcile.debit_move` / `credit_move` [restrict]

**Fuente.**
- `odoo19c: addons/account/models/account_partial_reconcile.py:15,18`: `debit_move_id`/`credit_move_id` required, sin `ondelete` → `restrict`.
- `unlink` de `account.move.line` (`odoo19c: addons/account/models/account_move_line.py:1984-2022`; abre con `if not self: return True`; `:1988 self.remove_move_reconcile()`): después comprueba bloqueo fiscal (`_check_fiscal_lock_dates`, solo líneas con saldo de asientos `posted`), `_check_tax_lock_date`, registra el borrado en el chatter si el asiento tuvo `posted_before` (sin `tracking_disable`), y ejecuta `super().unlink()` dentro de `move_id._check_balanced(...)` y `_sync_dynamic_lines(...)`.
- Guardas `@api.ondelete(at_uninstall=False)` del mismo archivo: `_unlink_except_posted` (`:1952-1959`, `UserError` si el asiento está `posted` y no hay `force_delete`), `_prevent_automatic_line_deletion` (`:1961-1973`, línea de impuesto o `payment_term` salvo `dynamic_unlink`), `_except_hashed_entry_lines` (`:1975-1982`, asiento con `inalterable_hash`).
- `remove_move_reconcile` (`:3138-3140`, completo):
```
3138    def remove_move_reconcile(self):
3139        """ Undo a reconciliation """
3140        (self.matched_debit_ids + self.matched_credit_ids).unlink()
```
- Dependencia directa: `account.partial.reconcile.unlink` (`odoo19c: addons/account/models/account_partial_reconcile.py:105-147`): (i) `_get_to_update_payments(from_state='paid')` para reponer pagos; (ii) busca los asientos de **caja base** por `tax_cash_basis_rec_id` y suma `exchange_move_id`; (iii) guarda `full_reconcile_id` y los apuntes; (iv) `super().unlink()` **primero**; (v) `full_to_unlink.unlink()`; (vi) revierte (`_reverse_moves(..., cancel=True)`) los asientos no borrador y borra los borrador; (vii) `_update_matching_number(all_reconciled.exists())`; (viii) pagos a `in_process`.
- `account.full.reconcile.unlink` (`odoo19c: addons/account/models/account_full_reconcile.py:47-60`): recalcula `matching_number` de las líneas.
- `account.move.unlink` (`odoo19c: addons/account/models/account_move.py:4055-4064`): `self.line_ids.remove_move_reconcile()` y luego `self.line_ids.unlink()` con `dynamic_unlink=True`, `skip_invoice_sync=True` — **segundo sitio que llama `remove_move_reconcile`**. Como `account.move.line.move_id` es `ondelete="cascade"` (`odoo19c: addons/account/models/account_move_line.py:32-41`), borrar un asiento con líneas conciliadas sólo funciona en la fuente por esta llamada previa.

**Nuestro árbol.**
- `AccountMoveLine(AnalyticMixin, models.Model)` (`account_move_line.py:35`), `AccountMove(SequenceMixin, models.Model)` (`account_move.py:27`), `AccountPartialReconcile(models.Model)`, `AccountFullReconcile(models.Model)`: **ninguno es `BaseModel`**; ninguno declara `unlink`, `remove_move_reconcile` ni `@api.ondelete` (`grep -n "def unlink\|def delete\|remove_move_reconcile\|ondelete" ...` sólo halla los dos `delete_and_update_matching`).
- `debit_move`/`credit_move`: `on_delete=models.CASCADE`, `related_name='matched_debit_ids'/'matched_credit_ids'` (`account_partial_reconcile.py:68-80`). `AccountMoveLine.move`: `CASCADE` (`account_move_line.py:55-60`).
- `AccountPartialReconcile.delete_and_update_matching` (`:156-175`) es el `unlink` simplificado: guarda `full_reconcile`, apuntes tocados; `super().delete()`; borra el full si queda sin parciales; `_update_matching_number(touched)`. Divergencias declaradas en la cabecera (`:23-46`): sin caja base (2), sin `exchange_move_id` (3), sin reapertura de pagos (4). `AccountFullReconcile.delete_and_update_matching` (`account_full_reconcile.py:69-79`) cubre el recálculo del full.
- Consumidores de esos `delete_and_update_matching`: sólo `tests/unit/account/test_account_reconcile.py:118,161`. Los wizards (`account_payment_register.py`, `account_automatic_entry_wizard.py`) sólo **crean** parciales (`create_partial`).
- `addons/account_fleet/models/account_move.py:224-229`: receptor `pre_delete` sobre `AccountMoveLine` como sustituto de `AccountMoveLine.unlink`. Con `PROTECT` un `pre_delete` llega tarde (el `Collector` rechaza al reunir): ver `designs/restrict-ondelete-non-company.md`, «Tramo A: la guarda llegaba tarde». No hace falta tocarlo, pero conviene saber que sigue corriendo.
- Consumidores de borrado de líneas/asientos: `tests/unit/purchase/test_purchase_invoice_link.py:97` (`bill_line.delete()`, línea sin parciales) es el único hallado por AST/grep sobre `AccountMoveLine`/`AccountMove`; no hay test que borre asientos con parciales (`grep -n "delete\|unlink" tests/integration/account/test_register_payment_endpoint.py` → vacío).

**Mínimo fiel propuesto** (sin inventar forma; cada paso lleva su cita):
1. `account.partial.reconcile` y `account.move.line` y `account.move` a `models.BaseModel, TimeStampedModel`-equivalente (precedente: `restrict-ondelete-payment-method-line.md` §6; verificar `makemigrations --check` vacío — **UNVERIFIED** aquí).
2. `AccountPartialReconcile.unlink` = el cuerpo de `delete_and_update_matching` reencuadrado a recordset (pasos (iii)-(v) y (vii) de la fuente; (i),(ii),(vi),(viii) siguen DEFERIDOS con las divergencias 2-4 ya declaradas). `delete_and_update_matching` pasa a alias o se retira (como se retiró la sobrescritura `delete` de `AccountPaymentMethod`).
3. `AccountMoveLine.remove_move_reconcile` ≙ `:3138-3140`: `(matched_debit_ids + matched_credit_ids).unlink()` (reversos de Django: `self.matched_debit_ids`/`matched_credit_ids` ya existen).
4. `AccountMoveLine.unlink`: `if not self: return True; self.remove_move_reconcile(); return super().unlink()`. Diferidos y declarados: bloqueo fiscal/impuestos, registro en chatter, `_check_balanced`/`_sync_dynamic_lines` y las tres guardas `@api.ondelete` (no portadas aquí).
5. `AccountMove.unlink`: `self.line_ids.remove_move_reconcile(); self.line_ids.unlink(); super().unlink()` — **obligatorio**: sin él, borrar un asiento con líneas conciliadas pasa a `ProtectedError` (la cascada `move→line` choca con el `PROTECT` de los parciales), mientras la fuente lo permite.
6. `debit_move`, `credit_move` → `PROTECT`; contrato: `delete()` crudo con parcial vivo → `ProtectedError`; `unlink` de la línea borra antes los parciales.

Incertidumbre fuerte (UNVERIFIED): tamaño de la adopción de `BaseModel` en `AccountMove` (modelo grande, `SequenceMixin`); si es excesivo, alternativa mínima es un `unlink` explícito de clase sin adoptar, pero entonces `Model.delete()` crudo no pasaría por él (mismo límite que `AccountPaymentMethod` resolvió con la adopción).

## 4. `stock.StockRule.picking_type` [restrict]

- Fuente: `odoo19c: addons/stock/models/stock_rule.py:87-90` `picking_type_id = Many2one('stock.picking.type', 'Operation Type', required=True, check_company=True, domain=...)`: required sin `ondelete` → `restrict` (`odoo/orm/fields_relational.py:274-282`).
- `stock.picking.type`: `odoo19c: addons/stock/models/stock_picking.py:20` abre la clase; `grep -n "def unlink\|api.ondelete" addons/stock/models/stock_picking.py` → sólo `:1170` (de `stock.picking`, no del tipo). Ninguna de las 10 extensiones Community (`stock_picking_batch`, `l10n_ar_stock`, `mrp`, `stock_account`, `stock_dropshipping`, `delivery_stock_picking_batch`, `repair`, `project_stock_account`, `l10n_it_stock_ddt`, `l10n_tr_nilvera_edispatch`) declara `unlink`/`@api.ondelete` sobre `stock.picking.type` (awk sobre cada archivo → sin salida). `odoo19c: addons/stock/models/stock_picking.py:49-51` `warehouse_id` del tipo es `ondelete='cascade'` (borrar un almacén arrastra sus tipos; con reglas vivas la base rehúsa).
- Nuestro estado: `addons/stock/models/stock_rule.py:545-556` `picking_type = Many2one('stock.StockPickingType', null=True, blank=True, on_delete=CASCADE, related_name='rule_ids')` (nullable, la fuente lo exige; divergencia previa de columna, fuera de esta fila). `StockPickingType(models.DefaultGetMixin, TimeStampedModel)` (`stock_picking.py:224`), sin `unlink`/`delete`; el `unlink` de `:1573` es de `StockPicking`. `StockPickingType.warehouse` `CASCADE` (`:289-293`) ya coincide con la fuente.
- Consumidores: `tests/unit/orm/test_delete_policy_contract.py:136-160` (`xfail` estricto «se rehúsa» y su gemelo «hoy se borra»); ningún test ni código borra tipos de operación (`grep` vacío). Único borrado de almacenes: `StockWarehouse.unlink` (`stock_warehouse.py:820-825`, sin invocadores en tests).
- **Propuesta:** `PROTECT` + `AlterField` + pasar la fila a `CORRECTED`; el caso «hoy se borra» (`test_today_deleting_a_picking_type_deletes_its_rules`, `:153-160`) debe invertirse o retirarse al mismo tiempo (cae exactamente ese caso y el `xfail` pasa a verde). Sin `unlink`.

## 5. Las 22 filas hacia `res.company`

Lista (la de `lot-0` §1, confirmada por `awk '$2=="restrict" && $1 ~ /ompany/' | wc -l` → 22): `account.{AccountBankStatementLine, AccountFiscalPosition, AccountGroup, AccountJournal, AccountLockException, AccountPayment, AccountReconcileModel, AccountReportExternalValue, AccountTax, AccountTaxGroup}.company`, `account_edi_proxy_client.AccountEdiProxyUser.company_id`, `analytic.AccountAnalyticLine.company`, `purchase.PurchaseOrder.company_id`, `purchase_requisition.PurchaseRequisition.company`, `sale.SaleOrder.company`, `stock.{StockPutawayRule, StockMoveLine, StockWarehouseOrderpoint, StockPackageHistory, StockPickingType, StockWarehouse}.company`, `website.Website.company`.

El padre: `res.company.unlink` sólo hace `super()` + `clear_cache` (`odoo19c: odoo/addons/base/models/res_company.py:347-353`, según `lot-0` §1).

### 5a. `AccountBankStatementLine.company`: `restrict` o `set null`

- Declaración: `odoo19c: addons/account/models/account_bank_statement_line.py:38-44`: `Many2one('res.company', inherited=True, related='move_id.company_id', store=True, readonly=False, precompute=True, index=False, required=True)`.
- `Many2one` sólo asigna `ondelete` en `setup_nonrelated` (`odoo19c: odoo/orm/fields_relational.py:267-282`). `Field.setup` bifurca: `if self.related: self.setup_related(model) else: self.setup_nonrelated(model)` (`odoo19c: odoo/orm/fields.py:541-544`). `setup_related` (`odoo/orm/fields.py:604-640`) no toca `ondelete` y `fields_relational.py` no define `setup_related` ni `_setup_attrs__` con `ondelete` (`_setup_attrs__` en `:253-262` sólo fija `delegate`). Resultado: `self.ondelete` queda `None` para un Many2one `related`.
- DDL: `update_db_foreign_key` usa `self.ondelete or 'set null'` (`odoo19c: odoo/orm/fields_relational.py:318`) ⇒ FK física **`ON DELETE SET NULL`**. La columna es NOT NULL por `required=True` (`odoo19c: odoo/orm/fields.py:1148-1181`, `update_db_notnull`; es columna almacenada, `store=True`).
- Efecto: borrar la empresa intenta poner NULL en una columna NOT NULL ⇒ `not_null_violation` ⇒ **el borrado se rehúsa**. El resultado observable es el de `restrict`, no el de `set null`; ni el atajo «required ⇒ restrict por defecto» (`:282`) ni el `ValueError` de `:283-288` se evalúan para un `related`. La etiqueta «restrict (defecto)» de la matriz (`fk_reference_ondelete.tsv` línea 614) es **inexacta en el mecanismo y correcta en la conducta**.
- Decisión: **`PROTECT`**. Con `SET_NULL` perderíamos la protección (nuestra columna es `null=True`, `account_bank_statement_line.py:118-122`) y borrar una empresa vaciaría la empresa de las líneas bancarias, justo lo que la fuente impide. Nota para el diseño: dejar la fila en la lista de 22 `PROTECT` pero con la nota de mecanismo; la clase `DESCONOCIDO` de `lot-0` pasa a **SOLO_ON_DELETE** con esta cita.
- UNVERIFIED: no hay DDL generado por una instancia de Odoo para confirmarlo (no hay base Odoo en este entorno); la conclusión sale de la lectura de `setup`/`update_db_*`.

### 5b. Consumidores que borran empresas (radio de impacto de `PROTECT`)

Método: `grep -rniE "(delete|unlink)\(" tests addons src | grep -iE compan` y un recorrido AST/regex (`/tmp/claude-0/.../scratchpad/co_del.py`) que localiza `ResCompany...delete()` y `x.delete()/x.unlink()` donde `x` es un nombre asignado desde `ResCompany.objects.create/get_or_create/get`, `ResCompany.create_company`, `_make_company` o la fixture `company`/`companies`. Resultado literal del recorrido:
```
1 tests/integration/base/test_migration_seeds_survive_flush.py       :210 ResCompany.objects.filter(code=_BOOTSTRAP_CODE).delete()
1 tests/integration/base_setup/test_company_delete_with_a_tableless_form.py :56 company.delete()
1 tests/integration/company/test_multidb_isolation.py                :356 ResCompany.objects.db_manager(alias).filter(pk=pk).delete()
1 tests/unit/base/test_ir_attachment.py                              :159 company.delete()
1 tests/unit/base/test_ir_model_data_loader.py                       :249 ResCompany.objects.filter(pk=pk).delete()
1 tests/unit/base/test_ir_model_data_xmlid.py                        :98  company.delete()
1 tests/unit/company/test_user_company_link.py                       :38  t.delete()
```
| Archivo (1 sitio cada uno) | Qué crea antes de borrar | ¿Depende de una cascada de las 22? |
|---|---|---|
| `tests/integration/base/test_migration_seeds_survive_flush.py:210` | `bootstrap_company_seed()` → `ResCompany.create_company` (`addons/sale_subscription/data/res_company_data.py:35-52`) | No: sólo empresa+partner |
| `tests/integration/base_setup/test_company_delete_with_a_tableless_form.py:56` | `ResCompany.objects.create` | No (el test vigila que el recolector no toque `SiteConfigSettings`, `DO_NOTHING`) |
| `tests/integration/company/test_multidb_isolation.py:356` | empresa por base; sólo `paperformat` | No |
| `tests/unit/base/test_ir_attachment.py:159` | empresa + `IrAttachment` (SET_NULL) | No (SET_NULL, no está entre las 22) |
| `tests/unit/base/test_ir_model_data_loader.py:249` | empresa + xmlid | No |
| `tests/unit/base/test_ir_model_data_xmlid.py:98` | fixture `company(db)` local (`:29`) | No |
| `tests/unit/company/test_user_company_link.py:38` | empresa + usuario (ya `PROTECT`, `ProtectedError` esperado) | No: precedente de que `PROTECT` hacia empresa ya existe |

- Código de producción: **0 sitios** que borren empresas (`src/addons/base/management/commands/` sólo tiene `company_create`, `company_migrate_all`, `cron`, `purge_logs`, `server`, `update_module_list`; no hay `destroy`/endpoint de empresa; `grep -rnE "company_delete|delete_company|drop_company"` vacío).
- Señales que podrían crear hijos de las 22 al crear una empresa: sólo `addons/account/models/res_company.py:835-841` (`load_chart_for_new_company`, y sólo si la empresa **tiene padre** con plan: `:882` `if not created or instance.parent is None: return`; y `check_audit_trail_on_save` en `pre_save`). El receptor de `stock` que crearía ubicaciones/tipos/reglas **no está conectado**: `addons/stock/handlers.py` sólo conecta `ReturnRequest`; los `_create_per_company_*` (`addons/stock/models/res_company.py:80-95,420`) son invocables a mano. `ResCompanyManager.create` (`src/addons/base/models/res_company.py:223-257`) sólo crea partner y moneda.
- Conclusión de radio: **7 archivos, 7 sitios, 0 con hijos `PROTECT`**; el cambio de las 22 filas no rompe ningún borrado de empresa conocido. Para las 22 filas, el único test que ejercita el comportamiento es el contrato (`tests/unit/orm/test_delete_policy_contract.py`).
- CIEGA A (declarado): nombres de variable fuera de la heurística (p. ej. empresas obtenidas por `ResCompany.objects.get_main_company()` o por fixtures con otro nombre); cadenas indirectas `padre.delete()` que cascadeen hasta una empresa (no existe tal FK hacia empresas desde padres con `CASCADE` hallada); y el comportamiento dinámico del `Collector` con varios niveles (la nota «Ciega a» de `restrict-ondelete-non-company.md` ya la declara).
- Interacciones a vigilar al activar `PROTECT` (no son sitios hoy): `StockWarehouse.company` es `CASCADE` y `null=False` (`stock_warehouse.py:321`) pero la lista lo marca `restrict`; al pasar a `PROTECT`, borrar una empresa con almacén se rehúsa, como en la fuente.

## 6. Orden sugerido (tras este lote)

1. Filas sólo-política sin `unlink`: `HrVersion.employee` (SET_NULL), `StockRule.picking_type` (PROTECT), las 22 de empresa (PROTECT, la de bank statement line con nota de mecanismo).
2. `ProjectTask.project`: adopción de `BaseModel` en `Project` + `unlink`, luego `SET_NULL`.
3. Tramo C: `remove_move_reconcile` + `AccountMoveLine.unlink` + `AccountMove.unlink` + `AccountPartialReconcile.unlink`, luego `PROTECT` en ambos apuntes.

## 7. Incertidumbres / UNVERIFIED

1. **Bank statement line (5a):** DDL real de Odoo no observado; la conclusión «set null físico sobre NOT NULL ⇒ rehúsa» sale de leer `setup`/`update_db_foreign_key`/`update_db_notnull`. UNVERIFIED por medición SQL.
2. **Tramo C (3):** el tamaño y el esquema de adoptar `BaseModel` en `AccountMove`/`AccountMoveLine`/`AccountPartialReconcile` (¿`makemigrations --check` vacío?, ¿conflictos con `AnalyticMixin`/`SequenceMixin`?) no se probó; riesgo del bloque.
3. **Project (2):** el orden entre `_check_project_group_at_removal` y el resto, y la limpieza de embedded actions (queda huérfana hoy), no se ejercitó; analítica BLOQUEADA por `account_id` ausente.
4. **HR (1):** la guarda `_unlink_except_last_version` (#525) no está portada; con `SET_NULL` conviven versiones huérfanas y la guarda debe tolerar `employee_id` vacío; cómo reaccionan `hr_work_entry`/`hr_skills` ante versiones huérfanas (no se leyeron).
5. **Radio de borrado de empresas (5b):** recorrido estático; variables con nombres no cubiertos y fixtures dinámicos quedan fuera. Además, `StockRule.picking_type` es `null=True` en nuestro modelo y `required` en la fuente (divergencia previa de columna, no tratada aquí).

## Comandos

```text
$ date -u +%Y-%m-%dT%H:%M:%SZ
2026-11-17T22:25:00Z
$ git -C /home/user/odoo-tools rev-parse --short=10 HEAD ; git status --porcelain | head -2
abe4040ec1
(sin salida)
$ awk 'NR>=4194 && NR<=4340 && /_inherits/' $R/odoo/orm/models.py | wc -l      # unlink de BaseModel no recorre _inherits
0
$ awk 'NR>=4194 && /^    def /&&NR>4194{print NR;exit}' $R/odoo/orm/models.py  # fin de unlink
4334
$ grep -n "def unlink\|api.ondelete" $R/addons/hr/models/hr_version.py $R/addons/hr/models/hr_employee.py
hr_version.py:294:    @api.ondelete(at_uninstall=False)
hr_employee.py:1473:    def unlink(self):
$ sed -n 46,53p $R/addons/hr/models/hr_employee.py     # version_id: store=False, ondelete='cascade'
        ondelete='cascade', required=True, store=False, compute_sudo=True ...
$ grep -n "def setup_related" $R/odoo/orm/fields_relational.py | wc -l
0
$ sed -n 541,544p $R/odoo/orm/fields.py
            if self.related:
                self.setup_related(model)
            else:
                self.setup_nonrelated(model)
$ sed -n 316,319p $R/odoo/orm/fields_relational.py
        model.pool.add_foreign_key(
            model._table, self.name, comodel._table, 'id', self.ondelete or 'set null',
$ sed -n 704,717p $R/addons/project/models/project_project.py
    def unlink(self): ... self.with_context(active_test=False).tasks.unlink() ... analytic_accounts_to_delete.unlink()
$ sed -n 3138,3140p $R/addons/account/models/account_move_line.py
    def remove_move_reconcile(self): ... (self.matched_debit_ids + self.matched_credit_ids).unlink()
$ sed -n 4055,4064p $R/addons/account/models/account_move.py
    def unlink(self): ... self.line_ids.remove_move_reconcile(); self.line_ids.unlink(); res = super().unlink()
$ for f in <10 extensiones Community de stock.picking.type>; do awk '/_inherit = .stock.picking.type./{f=1} f&&/def unlink|api.ondelete/' $f; done
(sin salida en las 10)
$ grep -n "^class \|def unlink\|def delete" addons/account/models/account_move_line.py addons/account/models/account_partial_reconcile.py | cut -c1-110
account_move_line.py:35:class AccountMoveLine(AnalyticMixin, models.Model):
account_partial_reconcile.py:156:    def delete_and_update_matching(self, *args, **kwargs):
$ python3 -I .../scratchpad/co_del.py       # 7 archivos / 7 sitios (ver §5b)
$ grep -rnE "sender=(ResCompany|'base\.ResCompany')" addons src
addons/account/models/res_company.py:836 ... :840
$ grep -n "post_save" addons/stock/handlers.py
13:from django.db.models.signals import post_save, pre_save   # sólo ReturnRequest (:23,:40)
```
