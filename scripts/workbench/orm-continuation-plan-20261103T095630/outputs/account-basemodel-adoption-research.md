<!-- Procedencia: subagente de investigación de sólo lectura (2026-11-24), nivel 3 de retención. Sin verificación independiente todavía; las cifras salen de los comandos citados en cada sección y sus scripts viven en el scratchpad de la sesión (intro.py, order.py, flips.py, count.sh). -->

# Investigación de solo lectura — `account` hacia `models.BaseModel`

Árbol: `/home/user/kaupamex-api` (sólo lectura). Referencia: `odoo19c`, `$O` =
`/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0` (sólo lectura). Forma de
partida: `outputs/stock-basemodel-adoption-research.md` (sección 6). Precedente de
`account.move`: `designs/account-move-basemodel-adoption.md` (paso C3, detenido).
Las clases y las relaciones salen de `django.setup()` con
`DJANGO_SETTINGS_MODULE=config.settings.testing` e introspección de `_meta`, sin
pytest, sin migraciones y sin conexión a la base.

## 0. Hallazgos que cambian el plan, antes de las tablas

1. **No hace falta una unidad de ACL.** A diferencia de `stock`, `addons/account/security/`
   existe, el manifiesto la declara (`addons/account/__manifest__.py:58-60`) y los 24 modelos
   tienen exactamente las filas de la fuente (sección 5).
2. **`account.move` ya se intentó y está detenido por una decisión que no es de código.**
   `designs/account-move-basemodel-adoption.md`, «Resultado: límite alcanzado, C3 detenido
   (2026-11-18)»: con `account.move` como `BaseModel`, `POST /api/v2/admin/finance/invoices/<id>/register-payment/`
   responde 403 en vez de 201 (el usuario tiene la capacidad del producto y ningún grupo contable de la
   fuente). La decisión (capacidades `HasCapability`/DEC-11 contra grupos de `ir.model.access`) sigue
   registrada como `dependency_blocked` en `outputs/continuation.jsonl:511`; el parche
   `outputs/orm-fk-delete-policy-contract-0515/c3-account-move-adoption.patch` existe. No encontré
   un registro posterior que la resuelva (último evento del archivo: `stock-basemodel-u6b-0397`,
   2026-11-24T02:38:12Z). **La U10 de la partición no es ejecutable sin esa decisión.**
3. **`account.account._order` no es válido para un `BaseModel`.** `addons/account/models/account_account.py:41`
   declara `_order = 'code, placeholder_code'`, y `placeholder_code` no es un campo del modelo
   (`order.py`, abajo: `bad=['placeholder_code']`). Hoy sólo se ordena por `Meta.ordering = ['code']`
   (comentario en `:39-40`). Un `BaseModel` ordena con `_order` (`src/orm/models.py:4515-4545`,
   `_check_qorder`): hay que portar el campo o declarar la divergencia **antes** de la U6.
4. **El motor de impuestos vive en un `QuerySet`, no en el modelo.** `AccountTaxQuerySet`
   (`addons/account/models/account_tax.py:235`, `objects = AccountTaxQuerySet.as_manager()` en `:785`)
   aloja 14 métodos, entre ellos `compute_all`. Un reverso que pasa a recordset (`product.taxes`,
   `line.tax_ids`) deja de ser un `QuerySet` y pierde esos métodos: hay que moverlos al modelo, como la fuente.

## 1. Las 24 clases fuera de `BaseModel`

Medido como lo mide `tests/unit/orm/test_basemodel_reach.py:33-44` (`model.__dict__.get('_name')`,
sin abstractos ni proxies): `account` tiene **33 modelos con `_name` propio, 24 fuera de `BaseModel`**,
y 9 ya son `BaseModel` (`account.move.line`, `account.partial.reconcile`, `account.full.reconcile`,
`account.journal`, `account.payment`, `account.payment.method`, `account.payment.method.line`, más los dos
transitorios `account.financial.year.op` y `account.setup.bank.manual.config`).
`account` está en `PENDING` (`test_basemodel_reach.py:48-53`) junto con `base`.

```bash
.venv/bin/python $S/intro.py   # django.setup(); TOTAL named 291, BM 218; bloque ACC por app
```

*Métrica:* `model.__dict__.get('_name')` por `apps.get_models()`, sin abstractos ni proxies.
*Ciega a:* un modelo de `account` sin `_name` propio (por ejemplo `AccountTaxAlternative`, `AccountTaxFormula`),
que el trinquete no mide.

Todas las bases directas son `(RecordLoaderMixin, models.Model)`; `AccountMove` añade `SequenceMixin`
(`sed -n 27p addons/account/models/account_move.py`). Ninguna lleva `TimeStampedModel` ni mixin de correo:
los `_inherit = ['mail.thread', …]` de `account.account`, `account.move`, `account.tax` y
`account.reconcile.model` son atributos declarados sin la clase mixin (precedente del paso contrario:
`account.journal` sí lleva `PortalMixin, MailThread, MailActivityMixin`, `account_journal.py:14-18`).

| `_name` | Clase | Archivo:línea | Líneas del archivo | Atributos de clase declarados | `save`/`delete`/`ondelete` propios |
|---|---|---|---|---|---|
| `account.account` | `AccountAccount` | `account_account.py:28` | 398 | `_name _inherit _description _order _check_company_auto _check_company_domain` | `save` `:304` (recalcula tipo/grupo/tags), `@api.ondelete` `:386` |
| `account.account.tag` | `AccountAccountTag` | `account_account_tag.py:40` | 172 | `_name _description` | `delete` `:148` (guarda de etiqueta maestra) |
| `account.bank.statement` | `AccountBankStatement` | `account_bank_statement.py:71` | 403 | `_name _description _order` | — |
| `account.bank.statement.line` | `AccountBankStatementLine` | `account_bank_statement_line.py:83` | 461 | `_name _description _order` | `save` `:295` (dos escrituras: INSERT y UPDATE de `internal_index`) |
| `account.cash.rounding` | `AccountCashRounding` | `account_cash_rounding.py:33` | 145 | `_name _description` | — |
| `account.fiscal.position` | `AccountFiscalPosition` | `account_fiscal_position.py:49` | 318 | `_name _description _order` | — |
| `account.fiscal.position.account` | `AccountFiscalPositionAccount` | `account_fiscal_position_account.py:19` | 82 | `_name _description _rec_name` | `save` `:79` |
| `account.group` | `AccountGroup` | `account_group.py:64` | 255 | `_name _description _order` | `save` `:250` (`super().save(update_fields=['parent'])`) |
| `account.incoterms` | `AccountIncoterms` | `account_incoterms.py:15` | 46 | `_name _description` | — |
| `account.journal.group` | `AccountJournalGroup` | `account_journal_group.py:17` | 67 | `_name _description` | — |
| `account.lock_exception` | `AccountLockException` | `account_lock_exception.py:49` | 165 | `_name _description` | — |
| `account.move` | `AccountMove` | `account_move.py:27` | 860 | `_name _inherit _description _order _mail_post_access _sequence_index _rec_names_search _mailing_enabled` | `save` `:845` (recalcula `store=True`) |
| `account.payment.term` | `AccountPaymentTerm` | `account_payment_term.py:146` | 582 (con la línea) | `_name _description _order` | — |
| `account.payment.term.line` | `AccountPaymentTermLine` | `account_payment_term.py:438` | (ídem) | `_name _description _order` | `save` `:579` |
| `account.reconcile.model` | `AccountReconcileModel` | `account_reconcile_model.py:69` | 383 (con la línea) | `_name _description _inherit _order` | `save` `:209` |
| `account.reconcile.model.line` | `AccountReconcileModelLine` | `account_reconcile_model.py:255` | (ídem) | `_name _inherit _description _order` | `save` `:379` |
| `account.report` | `AccountReport` | `account_report.py:174` | 877 (con las otras cuatro) | `_name _description _order` | — |
| `account.report.line` | `AccountReportLine` | `account_report.py:441` | (ídem) | `_name _description _order` | — |
| `account.report.expression` | `AccountReportExpression` | `account_report.py:562` | (ídem) | `_name _description _rec_name` | `save` `:703` (crea tags) |
| `account.report.column` | `AccountReportColumn` | `account_report.py:733` | (ídem) | `_name _description _order` | — |
| `account.report.external.value` | `AccountReportExternalValue` | `account_report.py:800` | (ídem) | `_name _description _order` | — |
| `account.tax` | `AccountTax` | `account_tax.py:745` | 3001 (con el `QuerySet`) | `_name _inherit _description _order _check_company_auto _rec_names_search _check_company_domain` | — |
| `account.tax.group` | `AccountTaxGroup` | `account_tax_group.py:23` | 131 | `_name _description _order` | `save` `:128` |
| `account.tax.repartition.line` | `AccountTaxRepartitionLine` | `account_tax_repartition_line.py:32` | 154 | `_name _description _order` | `save` `:149` |

```bash
grep -nE "^class |^    _name|^    _order|^    _[a-z_]+ = " addons/account/models/account_{account,account_tag,bank_statement,...}.py
grep -nE "def (write|create|unlink|delete|save)\b|@api.ondelete" addons/account/models/account_{...}.py
wc -l addons/account/models/account_{...}.py   # total 8500
```

Hallazgos de la tabla: **ninguna clase declara `write`, `create` ni `unlink`**, así que no hay
firmas `write(self, **vals)` ni `classmethod write` que reconciliar (a diferencia de `stock`). Las 11
`save` con lógica y el único `delete` (la etiqueta) son el trabajo de forma.

*Métrica:* `grep` de `def save|delete|write|create|unlink` y de `@api.ondelete` en los 18 archivos de modelo.
*Ciega a:* una sobrescritura que llegue por un mixin (`SequenceMixin`, `RecordLoaderMixin`) o por un parche
de `ready()` de otra app (7 sitios, sección 3).

### 1.1 `_order` y `Meta.ordering`

Medido con `order.py` (regex de `regex_order` y campos de `_meta`):

- Declaran `_order` igual que la fuente y su `Meta.ordering` coincide: 14 modelos. **Una excepción**, `account.account`
  (hallazgo 3). Otra diferencia de forma: `account.move` declara `_order` de cuatro claves y `Meta.ordering = ['-date','-id']`;
  un `BaseModel` ordena por `_order` (diseño de C3: «el orden … pasa de `Meta.ordering` al `_order`»).
- **Cinco modelos no declaran `_order` y sí `Meta.ordering`**: `account.cash.rounding` (`name`), `account.incoterms` (`code`),
  `account.journal.group` (`sequence, name`), `account.lock_exception` (`-id`), `account.report.expression` (`id`).
  La fuente tampoco declara `_order` en cash.rounding, incoterms, lock_exception ni expression
  (`grep -nE "^\s+_order" $O/addons/account/models/account_{cash_rounding,incoterms,lock_exception,report}.py`):
  el orden `Meta.ordering` es nuestro y un `BaseModel` ordenaría por `id`. Decisión de la unidad (U1 y U4).

*Métrica:* `_order` y `Meta.ordering` por `_meta`, y existencia de cada campo del `_order`.
*Ciega a:* un campo del `_order` que exista como campo no almacenado (no está en `_meta`) y sí se pueda ordenar
(`placeholder_code` no lo es; no ejecuté `_order_field_to_sql`).

## 2. Gráfica de relaciones

### 2.1 Entre los 24 (dueño → destino)

32 relaciones declaradas entre los 24; 21 pares distintos de nodos y **7 autorreferencias** (`account.group.parent`,
`account.report.root_report` y `section_reports`, `account.report.line.parent`, `account.tax.children`,
`original_tax_ids`, `replacing_tax_ids`). Tarjan (script en `$S`): **24 componentes, ninguno no trivial: no hay ciclos**
(a diferencia del ciclo `Warehouse↔PickingType↔Rule` de `stock`). Orden de la condensación, destinos primero:

`tag` → `account` → `tax.group` → `tax` → `fiscal.position` → `move` → `bank.statement.line`; independientes: `bank.statement`,
`cash.rounding`, `fiscal.position.account`, `group`, `incoterms`, `journal.group`, `lock_exception`,
`payment.term(.line)`, `reconcile.model(.line)`, `report(.line, .column, .expression, .external.value)`,
`tax.repartition.line`.

Aristas entre los 24: `account.tags→tag` · `statement.line→{move, statement}` · `cash.rounding→account×2` ·
`fiscal.position.tax_ids→tax` · `fiscal.position.account→{position, account×2}` · `move.fiscal_position_id→fiscal.position` ·
`payment.term.line→term` · `reconcile.model.line→{model, account}` · `report` y `report.line` / `column` / `expression` /
`external.value` (7 FK + 1 M2M) · `tax→tax.group` · `tax.group→account×3` · `repartition.line→{tax, account, tag}`.

### 2.2 Hacia y desde modelos que ya son `BaseModel`

Una relación cambia de tipo cuando sus dos extremos son `BaseModel`; `res.partner`, `res.company`, `res.users`, `res.currency`,
`res.country`, `ir.actions.*` **no lo son** (`base` está en `PENDING`), así que todo lo que sale hacia ellos o llega de ellos
(`company`, `partner`, `currency`, `country`, `create_uid`, `write_uid`, `property_account_*` de `res.partner`,
`account_sale_tax` de `res.company`, …) **no cambia hasta que `base` adopte**.

Relaciones que sí cambian de tipo, asignadas a la unidad que las cierra (el máximo de las unidades de sus dos extremos;
`flips.py`, con la partición de la sección 6): **62 relaciones**.

```bash
.venv/bin/python $S/intro.py     # bloque ALL: todo campo relacional con un extremo en los 24
python3 $S/flips.py              # asigna cada relación a la unidad que la cierra; "total 62"
```

| Unidad | Relaciones que cambian (dueño.campo → destino) |
|---|---|
| U1 (1) | `account.journal.group.excluded_journals → journal` (M2M; reverso `excluded_from_groups`) |
| U2 (2) | `product.template.account_tags → tag` (M2M; reverso `product_templates`) · `account.group.parent → group` (reverso `children`) |
| U3 (3) | `account.payment.term.line.payment → term` (reverso `line_ids`) · `sale.order.payment_term_id`, `purchase.order.payment_term_id → term` |
| U4 (8) | `root_report/variants`, `section_reports` (M2M), `report.line.report/lines`, `line.parent/children`, `expression.report_line/expressions`, `column.report/columns`, `external.value.target_report_expression/external_values`, `external.value.carryover_origin_report_line/carryover_external_values` |
| U5 (2) | `account.reconcile.model.match_journal_ids → journal` (M2M; reverso `reconcile_models`) · `reconcile.model.line.model → model` (reverso `line_ids`) |
| U6 (14) | hacia `account.account`: `account.move.line.account` (reverso `move_lines`), `account.journal.default_account`, `account.payment.outstanding_account_id`, `payment.method.line.payment_account` y `default_account_id`, `account.analytic.line.general_account`, `product.category.property_account_income_categ` y `_expense_categ`, `product.template.property_account_income` y `_expense`, `cash.rounding.profit_account` y `loss_account`, `reconcile.model.line.account`; y `account.account.tags → tag` (M2M) |
| U7 (14) | `product.template.taxes` y `supplier_taxes` (M2M), `sale.order.line.tax_ids`, `purchase.order.line.tax_ids` (M2M), `account.tax.tax_group`, `tax.children/original_tax_ids/replacing_tax_ids` (3 M2M), `tax.group.tax_payable_account/tax_receivable_account/advance_tax_payment_account`, `repartition.line.account/tax/tag_ids` |
| U8 (6) | `fiscal.position.tax_ids` (M2M), `fiscal.position.account.position/account_src/account_dest`, `sale.order.fiscal_position_id`, `purchase.order.fiscal_position_id` |
| U9 (3) | `bank.statement.journal`, `bank.statement.line.journal`, `bank.statement.line.statement` (reverso `line_ids`) |
| U10 (9) | `account.move.line.move` (reverso `line_ids`), `account.move.journal` (reverso `moves`), `account.move.fiscal_position_id`, `account.move.ubl_cii_xml_id → ir.attachment`, `bank.statement.line.move` (reverso `bank_statement_line`), `account.analytic.line.timesheet_invoice`, `account.edi.document.move_id`, `sale.order.invoice`, `purchase.order.invoice_ids` (M2M) |

*Métrica:* campos relacionales de `_meta.get_fields()` (concretos y M2M declarados) con un extremo en los 24 y el otro
`BaseModel` (hoy o en la partición); 62 de 175 filas del bloque ALL.
*Ciega a:* relaciones sin campo de Django (campos no almacenados `Many2one` de `orm/fields_nonstored.py`, que no están
en `_meta`), `Reference` genéricos, y los modelos sin `_name` propio que referencian a los 24 (`AccountTaxAlternative`,
`AccountMoveDebitNote`, `AccountMoveTransactionLink`, `AccountTaxFormula`, `AccountMoveLineTax*`, `SubscriptionInvoice`: todos
dueños no `BaseModel`, así que no cambian de tipo mientras no se les dé `_name`).

## 3. Usos que se rompen, por unidad

Método: para cada unidad se toman los archivos de `src/`, `addons/` y `tests/` que mencionan una clase de la unidad
(`\bAccountX\b`) o su `_name` literal, y sobre **ese** conjunto se buscan los accesores de la unidad. Esto evita contar `parent` o
`children` de `res.company`. Script: `count.sh`; `M` = `all|filter|exclude|add|set|remove|clear|count|exists|aggregate|first|last|order_by|values|values_list|create|get|update|delete|annotate`.

```bash
rg -l -P "\b(?:$C)\b|(?:$N)" $R --glob '*.py' --glob '!**/migrations/**'            # archivos con el modelo
… | xargs rg -n -P "\b(?:$A)\s+is\s+(?:not\s+)?None\b"                              # isNone
… | xargs rg -n -P "\.(?:$A)\.(?:$M)\("                                              # manager
… | xargs rg -n -P "\b(?:$C)\.objects\b"                                             # Cls.objects
… | xargs rg -n -P "\b(?:$C)\.objects\.[^\n]*\b(?:update|delete|bulk_create|bulk_update)\("
… | xargs rg -n -P "\.delete\(\)"                                                    # borrado de instancia
```

Formato de las celdas: líneas/archivos. «archivos» = archivos que mencionan el modelo.

| Unidad | Raíz | archivos | `is None` | gestor sobre accesores | `Cls.objects` | `objects.update/delete/bulk` | `.delete()` (cota superior) |
|---|---|---|---|---|---|---|---|
| U1 | src | 1 | 0 | 0 | 0 | 0 | 1/1 |
| | addons | 8 | 0 | 0 | 1/1 | 0 | 0 |
| | tests | 2 | 0 | 0 | 14/1 | 0 | 2/1 |
| U2 (tag) | src | 1 | 0 | 0 | 0 | 0 | 0 |
| | addons | 12 | 0 | 0 | 8/4 | 0 | 0 |
| | tests | 6 | 0 | 4/2 | 20/6 | 0 | 3/2 |
| U2 (group) | addons | 3 | 2/1 (`company.parent`, no es de `AccountGroup`) | 0 | 0 | 0 | 0 |
| | tests | 4 | 0 | 0 | 12/3 | 0 | 6/3 |
| U3 | addons | 8 | 0 | 5/1 | 0 | 0 | 1/1 |
| | tests | 6 | 0 | 0 | 41/5 | 0 | 2/1 |
| U4 | addons | 7 | 0 | 1/1 | 0 | 0 | 0 |
| | tests | 8 | 0 | 0 | 8/2 | 0 | 3/2 |
| U5 | addons | 4 | 0 | 3/2 | 0 | 0 | 0 |
| | tests | 3 | 0 | 3/1 | 11/2 | 0 | 4/2 |
| U6 | src | 2 | 0 | 0 | 0 | 0 | 1/1 |
| | addons | 40 | 0 | 5/2 | 14/8 | 0 | 2/2 |
| | tests | 37 | 0 | 15/2 | 108/32 | 1/1 | 9/3 |
| U7 | src | 2 | 0 | 0 | 0 | 0 | 12/1 |
| | addons | 37 | 1/1 | 15/5 | 4/2 | 0 | 4/2 |
| | tests | 29 | 1/1 | 22/8 | 98/24 | 0 | 9/6 |
| U8 | addons | 16 | 1/1 | 5/2 | 1/1 | 0 | 0 |
| | tests | 10 | 2/1 | 7/2 | 18/7 | 0 | 11/4 |
| U9 | addons | 8 | 0 | 4/2 | 3/2 | 0 | 0 |
| | tests | 2 | 0 | 0 | 19/1 | 0 | 2/1 |
| U10 | addons | 111 | 2/2 | 39/10 | 39/21 | 0 | 9/5 |
| | tests | 44 | 0 | 15/6 | 60/32 | 1/1 | 8/5 |

(U3-U10 con `src` vacío o sin archivos que mencionen el modelo: `files=0`.)

Detalle que la tabla no dice, leído línea a línea:

- **`is None` reales sobre accesores que cambian: 5.** `tests/unit/purchase/test_purchase_order_fiscal_header.py:72,95`
  (`order.fiscal_position_id is None`, cierra en U8); `addons/account/wizard/account_move_reversal.py:173`
  (`move.journal is not None and move.journal.active`, cierra en U10); `addons/sale/models/sale_order.py:932`
  (`position is not None and position.foreign_vat`, local de U8); `addons/account/models/product.py:238`
  (`tax is not None`, U7). Los demás aciertos son `company.parent`, `gateway.journal` (de pagos) o variables locales
  (`moves is not None`). **No hay recorridos `while x.parent`** (`rg "while\s+\w+…"` sobre `addons/account*` con `parent|group|node|current|line`: 0).
- **`move.line_ids.<gestor>`: 34 sitios** de los 46 de `line_ids.<gestor>` en `addons` y `tests` (el resto son `payment.term` 5,
  `bank.statement` 3, `reconcile.model` 4), repartidos así: `addons/account/models/account_move.py` 5 (`aggregate` ×3, `filter`, `exists`),
  `wizard/account_move_reversal.py` 4, `wizard/account_automatic_entry_wizard.py` 3, `chart_template.py` 2 (**`QuerySet.update` sobre líneas**:
  `transfer.line_ids.update(account=…)` `:1100`, `bank_fees.line_ids.update(account=…)` `:1106`, no invalida la caché de un recordset), `services.py` 1,
  `account_validate_account_move.py` 1, `account_payment_register.py` 1, `account_debit_note/wizard/account_debit_note.py` 1, `account_fleet/models/account_move.py` 1 en
  addons (19), y 15 en `tests/` (debit_note 5, invoice_from_sale 4, refund 2, register_payment_endpoint 2, subscription_ledger 2).
  Coincide en forma con la tabla de «17 sitios en 10 archivos» del diseño de C3; las cifras difieren porque esta suma incluye pruebas y `chart_template`.
- **Tax:** `.compute_all(`: 27 líneas en 5 archivos (18 en `tests/unit/account/test_account_tax_compute_all.py`, 5 en `account_tax_python`,
  2 en `account_tax.py`, 1 en `product.py`, 1 en `purchase_order_line.py`); `AccountTaxQuerySet`: 16 líneas en 6 archivos;
  `AccountTax.objects.<m>(`: 89 líneas en 26 archivos. Gestor sobre accesores de impuestos, línea a línea:
  `tax.children.all()` ×3 (`account_tax.py:271`, `account_update_tax_tags_wizard.py:204,334`), `.children.add/set` ×4 en pruebas,
  `self.tax_ids.all()` ×3, `product.supplier_taxes.all()` ×3, `producto.taxes.all().compute_all(…)` (`account_tax.py:59`),
  `self.repartition_lines.filter(...)`, `fiscal_positions.add`, `original_tax_ids.add/set`, `replacing_tax_ids.all()`.
- **`write`/`unlink`:** no hay `def write|unlink|create` en los 18 archivos (sección 1); el único `@api.ondelete` es
  `AccountAccount._unlink_except_linked_to_fiscal_position` (`account_account.py:386-398`).
- **Extensiones por otras apps:** `_inherit = 'account.move'` de 7 addons (`account_debit_note`, `account_peppol_advanced_fields`,
  `sale_timesheet`, `account_payment`, `account_peppol`, `account_edi`, `account_edi_ubl_cii`), `'account.tax'` de 3
  (`account_tax_python`, `l10n_mx`, `account_edi_ubl_cii`) y `'account.account'` de 1 (`l10n_mx`), todas declaradas como
  clases que parchean en `ready()` (`rg -nE "_inherit\s*=…account\.(…)"`). Importadores de la clase: `AccountMove` 32 archivos, `AccountAccount` 10, `AccountTax` 6,
  `AccountFiscalPosition` 2, `AccountPaymentTerm` 2, `AccountBankStatementLine` 2, `AccountReport` 1.

*Métrica:* `rg` sobre los archivos que mencionan el modelo, con el patrón literal de cada accesor.
*Ciega a:* un accesor con el mismo nombre en otro modelo dentro de un archivo que menciona el modelo (`tax_ids` aparece también en
`purchase.order.line`), un reverso usado por una variable local (`m = x.line_ids; m.filter(…)`), `getattr(obj, 'name')`, `values().annotate()`
sobre instancias, plantillas de informe, los 12 archivos de `account_*` de `l10n` o datos `*.py` de `data/`, y el comportamiento en ejecución
(en `account.move`, el diseño de C3 midió 46 fallos con la base sola, de los cuales 44 son gestor y 35 `PermissionDenied`; esa cifra es de su pase y no se re-midió).

## 4. `prefetch_related`, `select_related`, `annotate`

Los lookups de consulta (`filter(account__code=…)`, `Q(tax_group__…)`) pasan por SQL y **no cambian** al adoptar. Lo que sí cambia es la lectura
de instancia y su caché: `save()` y `QuerySet.update` ya no invalidan la caché de un recordset (en `account.move.line` el diseño de C3 midió un caso:
`test_migration_0039_fills_the_existing_lines`). Sitios `QuerySet.update/delete/bulk` sobre las clases: **2** (`tests` en U6 y U10: 1 y 1).

```bash
rg -n -P "\b(?:AccountAccount)\.objects\.[^\n]*\b(?:update|delete|bulk_create|bulk_update)\(" tests
```

*Métrica:* las dos celdas `objects.update/delete/bulk` de la sección 3. *Ciega a:* un `update` por variable local (`qs = X.objects.filter(...); qs.update(...)`).

## 5. ACL

- `addons/account/security/ir.model.access.csv` existe (120 líneas, 99 filas) y el manifiesto lo carga (`__manifest__.py:58-60`),
  junto con `security/account_security.xml` (grupos `account.group_account_manager/user/invoice/readonly/basic`).
  La fuente trae 146 líneas (125 filas).
- **Para los 24 modelos: 71 filas en la fuente y 71 filas locales**, igual por modelo (`python3` con `csv.DictReader`,
  `model_id:id == 'model_' + _name.replace('.','_')`). No falta ninguna.
- **Por modelo** (idéntico en ambos lados): `account` 5 · `account.tag` 4 · `bank.statement` 3 · `bank.statement.line` 3 · `cash.rounding` 2 ·
  `fiscal.position` 2 · `fiscal.position.account` 2 · `group` 3 · `incoterms` 2 · `journal.group` 3 · `lock_exception` 2 · `move` 3 ·
  `payment.term` 3 · `payment.term.line` 2 · `reconcile.model` 3 · `reconcile.model.line` 3 · `report` 3 · `report.column` 3 ·
  `report.expression` 3 · `report.external.value` 2 · `report.line` 3 · `tax` 4 · `tax.group` 4 · `tax.repartition.line` 4.
- **Lo que sí importa para el riesgo, y es una variación entre modelos:** sólo **11 de los 24** tienen una fila de lectura para `base.group_user`
  (`account`, `tag`, `fiscal.position`, `fiscal.position.account`, `incoterms`, `lock_exception`, `payment.term`, `payment.term.line`, `tax`,
  `tax.group`, `tax.repartition.line`). Los otros **13** exigen un grupo contable: `bank.statement` y su línea, `cash.rounding`, `group`,
  `journal.group`, `move`, `reconcile.model` y su línea, y las cinco de `report`. Ésos son los que producen `PermissionDenied` en pruebas sin usuario ni `sudo`
  y el 403 de la ruta de pago (diseño de C3).
- **Regla de registro omitida:** `account_comp_rule` no está portada porque `account.account` tiene `company` singular y no el M2M `company_ids`
  (cabecera de `account_security.xml:20-24`, sucesor `account-account-company-ids-0121`). Al adoptar, `account.account` queda con ACL y sin esa regla
  de empresa: es el modelo de la U6 donde la omisión pesa.

```bash
python3 - <<'EOF'   # filas por modelo, referencia y local; "ref 125 71 / local 99 71"
EOF
```

*Métrica:* filas del CSV cuyo `model_id:id` es uno de los 24.
*Ciega a:* si el usuario de cada prueba pertenece al grupo que la fila nombra, y a las reglas de registro (`ir.rule`) que no se portaron.

## 6. Partición propuesta (en orden de dependencia)

Criterio: igual que en `stock` y `sale`, un reverso o Many2one sólo cambia de tipo cuando ambos extremos son `BaseModel`; cada unidad cae en las
relaciones que cierra (columna «accesores que cambian», con la cuenta de la sección 2.2). El orden sigue la condensación de la gráfica (no hay ciclos),
con tres ajustes de riesgo: (i) las unidades que sólo cierran relaciones entre catálogos van primero, (ii) `account.account` precede a `account.tax`
para que `tax.group`, `repartition.line` y `fiscal.position.account` cierren sus relaciones hacia la cuenta en su propia unidad, (iii) `account.move` va
último porque es el que concentra el reverso `line_ids` (34 sitios de gestor) y porque está detenido por una decisión externa.

| Unidad | Contenido | Por qué en este orden | Accesores que cambian | Riesgos |
|---|---|---|---|---|
| **U0 — precondiciones, sin código** | (a) decisión sobre capacidades y grupos para el dominio contable (la de C3); (b) decidir `placeholder_code`; (c) criterio de `Meta.ordering` sin `_order` (5 modelos) | Las tres bloquean una unidad concreta (a: U10; b: U6; c: U1 y U4); registrarlas antes de abrir cualquier unidad evita el patrón de C3 (cambio hecho, decisión después) | ninguno | (a) es de otra autoridad y ya está bloqueada desde el 2026-11-18 |
| **U1 — catálogos hoja** | `AccountIncoterms`, `AccountLockException`, `AccountCashRounding`, `AccountJournalGroup` (423 líneas en 4 archivos) | Sin `save` ni `delete`, con 0 `is None` y 0 gestor sobre accesores (tabla §3); cada uno tiene 0-1 relación hacia un `BaseModel` (`journal.group.excluded_journals`) | 1: `excluded_journals` y su reverso `excluded_from_groups`; `cash.rounding.profit_account/loss_account` esperan a U6 | 3 `_order` implícitos que pasan de `Meta.ordering` a `id` (`incoterms code`, `cash.rounding name`, `journal.group sequence,name`; `lock_exception -id`): decisión U0(c); `journal.group` y `cash.rounding` no tienen fila para `base.group_user` (§5) |
| **U2 — árbol de grupos y etiquetas** | `AccountGroup`, `AccountAccountTag` (427 líneas) | Independientes entre sí y sin dependencia de los demás; juntos porque ambos traen un enganche de forma (`group.save` con `update_fields=['parent']`; `tag.delete` → `@api.ondelete`), el mismo tipo de trabajo | 2: `account.group.parent`/`children` (autorreferencia), `product.template.account_tags`/`product_templates` (M2M) | `_unlink_except_master_tags` pasa de `delete()` a `@api.ondelete`; `group.save` tiene que migrar a `create/write`; 6 `.delete()` de pruebas sobre grupos; 4 sitios de gestor en pruebas sobre `product_templates` |
| **U3 — condiciones de pago** | `AccountPaymentTerm`, `AccountPaymentTermLine` (582 líneas, un archivo) | Cierra `sale.order.payment_term_id` y `purchase.order.payment_term_id`, que ya son `BaseModel`; la línea es hija directa, no hay cadena | 3: `line.payment`/`line_ids`, `sale.order.payment_term_id`, `purchase.order.payment_term_id` | 5 sitios de `line_ids.<gestor>` (`account_payment_term.py:232,244,366,560,573`: `exclude(pk=…).order_by('id')`, `count`, `all`); `PaymentTermLine.save` con `_check_percent`; `payment.term` tiene fila `base.group_portal` |
| **U4 — familia de informes** | `AccountReport`, `AccountReportLine`, `AccountReportExpression`, `AccountReportColumn`, `AccountReportExternalValue` (877 líneas) | Cinco modelos cerrados entre sí: sus 8 relaciones son internas, y ninguna llega a un `BaseModel` externo, así que es el mayor bloque sin consumidores de otras apps (1 línea de gestor en addons, 0 `is None`) | 8 internas (root/variants, section, lines, children/parent, expressions, columns, external_values, carryover) | `AccountReportExpression.save` (`:703`) crea tags: pasar a `create/write`; `report.expression` sin `_order` y con `Meta.ordering = ['id']`; las 5 sin fila para `base.group_user`; `account.report.line.action` y `column.custom_audit_action` apuntan a `ir.actions.*` (no cambian) |
| **U5 — modelos de conciliación** | `AccountReconcileModel`, `AccountReconcileModelLine` (383 líneas) | Cierra `match_journal_ids` contra `account.journal`; la relación hacia `account.account` espera a U6 | 2: `match_journal_ids`/`reconcile_models` (M2M), `line.model`/`line_ids` | `_inherit = ['mail.thread']` y `analytic.mixin` sin la clase mixin (decidir si se añaden); 2 `save` con cálculo (`_check_match_label_param`, `_compute_float_amount`/`_validate_amount`); 3+1 sitios de `line_ids.<gestor>` en `chart_template` (`fee_rule.line_ids.count/get`) |
| **U6 — `account.account`** | `AccountAccount` (398 líneas) | Eje con más reversos entrantes ya `BaseModel` (10 dueños: `move.line`, `journal`, `payment`, `payment.method.line` ×2, `analytic.line`, `product.category` ×2, `product.template` ×2); precede a `tax` para que sus tres campos de `tax.group` y el de `repartition.line` cierren en U7 | 14: los de la tabla §2.2 (incluye `account.move.line.account`/`move_lines`, `journal.default_account`, `cash.rounding.profit/loss_account`, `reconcile.model.line.account`, `account.tags`) | **`_order` con `placeholder_code` no es campo** (U0 b); `save` recalcula tipo, grupo y tags (`:304-312`); `@api.ondelete` ya existe y sólo cambia de contrato (`:386`); `l10n_mx` extiende `account.account`; 108 `AccountAccount.objects` en 32 archivos de pruebas (el gestor `objects` sigue), 15 sitios de gestor en pruebas (2 archivos), 1 `objects.update`, 9 `.delete()`; falta `account_comp_rule` (§5); `test_chart_template.py:640` |
| **U7 — impuestos** | `AccountTaxGroup`, `AccountTax`, `AccountTaxRepartitionLine` (3286 líneas, de las que 3001 son `account_tax.py`) | Después de U2 (tag) y U6 (account); `tax.group` primero, `tax` después y `repartition.line` al final, todo en una unidad porque el motor `compute_all` cruza los tres | 14: `product.template.taxes/supplier_taxes`, `sale.order.line.tax_ids`, `purchase.order.line.tax_ids`, `tax.tax_group`, 3 M2M de `tax` consigo mismo, 3 de `tax.group`→cuenta, 3 de `repartition.line` | **El motor vive en `AccountTaxQuerySet` (14 métodos)**: mover `compute_all`, `_flatten_taxes_and_sort_them`, `_get_tax_details`, etc. al modelo (27 llamadas a `.compute_all(` en 5 archivos, 16 líneas de `AccountTaxQuerySet` en 6, 89 `AccountTax.objects.<m>(` en 26); `objects = AccountTaxQuerySet.as_manager()` (`:785`) frente a un `BaseModel`: no medido; 22+15 sitios de gestor sobre `taxes`, `tax_ids`, `children`, `repartition_lines`; `TaxGroup.save`, `RepartitionLine.save` con `_compute_factor`; extensiones de `account_tax_python`, `l10n_mx`, `account_edi_ubl_cii`; `product.py:238 tax is not None` |
| **U8 — posiciones fiscales** | `AccountFiscalPosition`, `AccountFiscalPositionAccount` (400 líneas) | Necesita U6 y U7: `fiscal.position.tax_ids` (M2M a `tax`) y `position.account` (dos FK a `account`) cierran aquí; el reverso `moves` espera a U10 | 6: `tax_ids`/`fiscal_positions`, `position`/`account_ids`, `account_src/dest`, `sale.order.fiscal_position_id`, `purchase.order.fiscal_position_id` | 2 `is None` en pruebas (`test_purchase_order_fiscal_header.py:72,95`) y `sale_order.py:932`; 11 `.delete()` de pruebas; `FiscalPositionAccount.save` rellena `company`; 5+7 sitios de gestor (`position.tax_ids.set/add`, `original_tax_ids.add`) |
| **U9 — extractos bancarios** | `AccountBankStatement`, `AccountBankStatementLine` (864 líneas) | Cierra `journal` (ya `BaseModel`) y `statement`/`line_ids`; `line.move` espera a U10 | 3: `statement.journal`, `statement.line.journal`, `statement.line.statement`/`line_ids` | `StatementLine.save` hace INSERT y luego un UPDATE de `internal_index` (`:295`): es el único `save` con dos escrituras; 3 `line_ids.<gestor>` en `account_bank_statement.py:212,263,281` (`exclude(internal_index='')`); sin fila `base.group_user` (acceso `group_account_basic/readonly/invoice`) |
| **U10 — `account.move`** | `AccountMove` (860 líneas) | Último: cierra el reverso más usado (`line_ids`, 34 sitios) y depende de U8 (`fiscal_position_id`) y de U9 (`bank_statement_line`); **bloqueado por U0(a)** | 9: `move.line.move`/`line_ids`, `move.journal`/`moves`, `move.fiscal_position_id`, `move.ubl_cii_xml_id`, `statement.line.move`, `analytic.line.timesheet_invoice`, `edi.document.move_id`, `sale.order.invoice`, `purchase.order.invoice_ids` | El diseño de C3 midió **46 fallos y 2 errores sobre 5 691**: 44 por `line_ids` como gestor, 3 `PermissionDenied`, 1 por `QuerySet.update` sin invalidar caché; y tras convertir los 17 sitios quedaron 46 sobre 5 696, de ellos 35 `PermissionDenied` y 4 con 403 en la ruta `register-payment`. 7 addons extienden `account.move`; `move.save` recalcula `store=True`; `AccountMove.unlink` (`remove_move_reconcile` → `line_ids.unlink()` → `super().unlink()`) es lo que desbloquea `C4` de `orm-fk-delete-policy-contract-0515` |

Peso estimado de los dos ejes grandes, por lo medido y no por un conteo de líneas:

- **`account.tax` (U7)** es el mayor por tamaño (3001 de 8500 líneas del bloque, 35 %) y por obra de forma: hay que **mover 14 métodos de un `QuerySet` al
  modelo** y reescribir sus receptores (27 `.compute_all(` + el `.all().compute_all(` de `product.py`). Sus reversos entrantes son M2M (`product.taxes`,
  `line.tax_ids`), de los que `.add/.set/.all` suman 37 líneas en `addons/` y `tests/`. No tiene decisión externa pendiente.
- **`account.move` (U10)** es menor por tamaño (860 líneas) y el mayor por riesgo medido: 34 sitios de `line_ids.<gestor>`, 7 extensiones de otras apps y
  una decisión de autoridad pendiente que ya detuvo un intento. Su trabajo mecánico (los 17 sitios y las pruebas) ya existe como parche.

Orden de ejecución sugerido de las verificaciones por unidad (igual que en `stock`): subconjunto derivado con el comando de
`alcance-de-la-suite.md` sobre los símbolos de la unidad, control de anulación de cada conversión de sitio, y `test_basemodel_reach.py`
(el trinquete sigue en `PENDING` hasta U10: el conjunto `NAMED['account'] - BM` va bajando, pero `account` no sale de `PENDING` hasta que no quede ninguno,
mientras `_outside('account')` no esté vacío).

**Alternativa evaluada y descartada:** adoptar los 24 de golpe. Descartada porque sólo `account.move` ya costó 46 fallos con 17 sitios cerrados y una decisión
abierta, y porque `account.tax` exige reubicar un motor de 14 métodos; un subconjunto rojo de esa extensión no atribuye causa.

## 7. Primera unidad recomendada

**U1 (catálogos hoja).** Es la única sin trabajo de forma más allá de `_order` y con 0 usos que se rompen en `src/` y `addons/`; fija las decisiones
transversales con el menor radio (criterio de `Meta.ordering` sin `_order`, el patrón de `ModelAccess` sin fila para `base.group_user`, y si se añaden las
clases mixin) antes de tocar `account.account` o `account.tax`. En paralelo debe registrarse la decisión U0(a) para que U10 no vuelva a detenerse tras hacer el trabajo.

*Métrica:* cifras de §1 a §5 (comandos citados en cada sección), pesos por `wc -l`, relaciones por `flips.py`.
*Ciega a:* el costo real en pruebas, que sólo una ejecución del subconjunto rojo mide; un consumidor por plantilla de informe o por `data/*.py`; el modo en que
`objects = AccountTaxQuerySet.as_manager()` convive con `BaseModel` (no ejecutado); y la decisión de capacidades de U0(a), que no es medible desde el árbol.
