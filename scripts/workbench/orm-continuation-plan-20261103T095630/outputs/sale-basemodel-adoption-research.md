<!-- Informe de un subagente de investigación (nivel 3 al recibirlo). Verificado por el orquestador el 2026-11-22T16:20:51: sin CSV en addons/sale/security; SaleOrderLine.delete en sale_order_line.py:724; precedente PurchaseOrder (purchase_order.py:122); descriptor docs.order_line.all en report_templates.py:57. CORRECCIÓN: la fuente trae 11 filas de ACL para model_sale_order/model_sale_order_line (grep -c sobre odoo19c: addons/sale/security/ir.model.access.csv), no 13. -->

# Investigación de solo lectura — `sale.order` y `sale.order.line` hacia `models.BaseModel`

Árbol medido: `/home/user/kaupamex-api-wt-u2` (HEAD `942b2d75`). Referencia: `odoo19c` (`$O` =
`/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0`). Todo lo de abajo salió de comandos de
este turno (grep, sed, y `django.setup()` + introspección de `_meta`, sin pytest, sin escribir en el repo).

## 1. Bases, y qué hay que marcar

`SaleOrder` — `addons/sale/models/sale_order.py:129-130`:
`class SaleOrder(PortalMixin, ProductCatalogMixin, MailThread, MailActivityMixin, UtmMixin, AccountDocumentImportMixin, TimeStampedModel)`.
`SaleOrderLine` — `addons/sale/models/sale_order_line.py:31`: `class SaleOrderLine(AnalyticMixin, TimeStampedModel)`.
Ambos declaran `_name` (`sale_order.py:195`, `sale_order_line.py:43`) y `_inherit` (`:202`, `:52`).

Estado de cada padre (medido con `orm.model_classes.is_abstract` sobre el MRO; `check_model_bases` es
`src/orm/model_classes.py:1166`, sólo mide padres con `_name`; el chequeo es `:1151`):

| Padre | `_name` | abstracto | Acción |
|---|---|---|---|
| `PortalMixin` (`addons/portal/models/portal_mixin.py:36`, `Meta.abstract` en `:57`) | no | sí | nada |
| `ProductCatalogMixin` (`addons/product/models/product_catalog_mixin.py:102`) | no | clase plana | nada (no lo mide el check) |
| `MailThread` (`addons/mail/models/mail_thread.py:42`, `_name` `:51`, abstract `:62`) | `mail.thread` | sí | nada |
| `MailActivityMixin` (`addons/mail/models/mail_activity_mixin.py:122,127,131`) | `mail.activity.mixin` | sí | nada |
| `UtmMixin` (`addons/utm/models/utm_mixin.py:64,69,124`) | `utm.mixin` | sí | nada |
| `AccountDocumentImportMixin` (`addons/account/models/account_document_import_mixin.py:178,185`) | `account.document.import.mixin` | sí por `_abstract = True` (`:581`) | nada |
| `TimeStampedModel` (`src/addons/base/models/timestamped_mixin.py:85`, abstract `:147`) | no | sí | nada |
| `AnalyticMixin` (`addons/analytic/models/analytic_mixin.py:75`, abstract `:87`) | no | sí | nada |

Conclusión: **no hay padre que marcar**. El único cambio de bases es anteponer `models.BaseModel`, como el
precedente `PurchaseOrder` (`addons/purchase/models/purchase_order.py:122-124`, que ya hereda
`PortalMixin, ProductCatalogMixin, MailThread, MailActivityMixin, AccountDocumentImportMixin,
TimeStampedModel`, es decir los mismos mixins que sale menos `UtmMixin`) y `PurchaseOrderLine`
(`addons/purchase/models/purchase_order_line.py:83`, `(models.BaseModel, AnalyticMixin, TimeStampedModel)`).
`UtmMixin` sí lo hereda `CrmLead` ya adoptado (`addons/crm/models/crm_lead.py:165`).

Lo que SÍ falta y no es una base: **ACL**. `addons/sale/` no tiene `security/ir.model.access.csv` ni lo
declara el manifiesto (el `grep "security|csv"` sobre `addons/sale/__manifest__.py` da 0 líneas; sólo existe
`addons/sale/security/ir_rules.py`). Los adoptados sí (`addons/purchase/__manifest__.py:39-40`,
`addons/website/__manifest__.py:28-29`, `addons/crm/__manifest__.py:37-38`). La fuente trae 13 filas para los
dos modelos (`$O/addons/sale/security/ir.model.access.csv:28-39`: portal, readonly, invoicing_payments,
accountant, salesman, manager para order; los mismos cinco/seis para line, con salesman 1,1,1,1 en line).
Sin esas filas un `BaseModel` rehúsa lecturas a quien no sea `su`: en la adopción de `account.move` ese fue el
origen de 3 `PermissionDenied` en tests sin usuario ni `sudo` (`designs/account-move-basemodel-adoption.md`).

## 2. `save()` y `delete()` propios

| Método | Qué hace | Contraparte en la fuente | Qué pasa con `BaseModel` |
|---|---|---|---|
| `SaleOrder.save` (`sale_order.py:1061-1105`) | si cambió `company_id` desde la carga (`_loaded_company_id`, poblado por `from_db` `:1047-1059`), corre `_compute_validity_date` y añade `validity_date` a `update_fields` | `@api.depends('company_id')` de `validity_date`, compute `store`+`precompute` (`$O/addons/sale/models/sale_order.py:220`). El otro disparo (precompute al crear) ya vive en el motor (`orm/models.py::_add_precomputed_values`) | **Sigue corriendo**: `BaseModel.write` termina en `save(update_fields)` por registro (hecho de la unidad website). `from_db` llama `super()`, que con `BaseModel` primero resuelve a `BaseModel.from_db`: probar que `_loaded_company_id` sigue poblándose |
| `SaleOrderLine.save` (`sale_order_line.py:700-722`) | `_coerce_amount_operands`; en modificación recalcula importes y precios reducidos y amplía `update_fields` con `COMPUTED_AMOUNT_FIELDS`; después `self.order._compute_amounts()` | `_compute_amount` store+precompute (`$O/.../sale_order_line.py`, motor de dependencias); `SaleOrder._compute_amounts` por `@api.depends('order_line.price_*')` (`$O/.../sale_order.py:513`) | Sigue corriendo vía `write`/`create`. Diseño previo: `designs/eager-computes-in-save.md` |
| `SaleOrderLine.delete` (`sale_order_line.py:724-728`) | guarda `order = self.order`, `super().delete()`, `order._compute_amounts()` | en la fuente es `@api.ondelete(at_uninstall=False) _unlink_except_confirmed` (`$O/.../sale_order_line.py:1469-1472`, usa `_check_line_unlink` `:1450-1466`) más el recálculo por dependencia; no hay `delete` | **Se salta en silencio**: `BaseModel.unlink` (`src/orm/models.py:9094`) borra por queryset (`rows.delete()`), no llama `delete()` de instancia. Hay que portarlo a `unlink()`: `orders = self.order` antes, `super().unlink()`, luego `for o in orders: o._compute_amounts()` (`_compute_amounts` es de un solo registro: `sale_order.py:1141-1145` hace `self.save`). Cuidar el borrado en cascada de la orden: ni hoy ni después pasa por el `delete()` de la línea |

No hay `create`, `write`, `unlink` ni `@api.ondelete` propios en los dos archivos (`grep "def create|def write|def unlink|ondelete|constrains"` sobre ambos
sólo devuelve `save` en `:1061` y `:700`, `delete` en `:724`, y menciones de `ondelete='...'` de campos).
Brechas contra la fuente, **no** introducidas por la adopción pero que la adopción hace portables
(decisión de comportamiento, no mecánica):
- `SaleOrder`: `create` que asigna `name` por secuencia (`$O/.../sale_order.py:1004-1013`; aquí `name` se asigna en `confirm`, `sale_order.py:1214`, vía `_next_sale_name` `:44-60`), `_unlink_except_draft_or_cancel` (`:1032-1038`), `write` que prohíbe cambiar tarifa en `sale` (`:1040-1043`), `@api.constrains('company_id','order_line')` (`:848`) y `('prepayment_percent')` (`:865`).
- `SaleOrderLine`: `create` (`:1322`), `write` (`:1364`), `_unlink_except_confirmed` (`:1469`), `@api.constrains('combo_item_id')` (`:1293`).
Portar `_unlink_except_*` cambia comportamiento (hoy una orden `sale` o una línea de orden confirmada se borra); no
se debe mezclar con la adopción mecánica.

## 3. Accesores que cambian de tipo

Regla (descriptores `src/orm/models.py:6469` `_x2many_descriptor_get` y `src/orm/fields.py:1508`
`NonStoredMany2oneAccessor`): un x2many es recordset sólo si **dueño y comodelo** son `BaseModel`. Medido
instanciando un `PurchaseOrder` (BaseModel) en memoria: un Many2one nulo a comodelo BaseModel devuelve una
instancia vacía del modelo (`requisition`, `purchase_group`), y a comodelo no BaseModel devuelve `None`
(`partner_id`, `company_id`, `picking_type`...).

Estado BaseModel de los comodelos (medido con `issubclass(m, BaseModel)`): SÍ — `sales_team.CrmTeam`,
`sales_team.CrmTag`, `account.AccountJournal`, `account.AccountPaymentMethodLine`, `account.AccountMoveLine`,
`product.ProductPricelist`, `product.ProductProduct`, `product.ProductComboItem`,
`product.ProductTemplateAttributeValue`, `uom.Uom`, `utm.*` (campaign/source/medium). NO — `base.ResPartner`,
`base.ResUsers`, `base.ResCompany`, `base.ResCurrency`, `base.ResCountry`, `account.AccountMove`,
`account.AccountFiscalPosition`, `account.AccountPaymentTerm`, `account.AccountTax`, `mail.MailTemplate`,
`delivery.ShippingMethod`. (Coherente con `PENDING = {account, base, sale, stock}` en
`tests/unit/orm/test_basemodel_reach.py:48-53`; la app `sale` tiene exactamente dos modelos con `_name`, los dos
de esta unidad, así que `sale` sale de `PENDING` al adoptar ambos. Medido: `apps.get_app_config('sale').get_models()` →
SaleOrder, SaleOrderLine.)

### 3.1 Accesores que pasan a recordset al adoptar los DOS modelos

| Accesor | Origen | Usos de API de gestor en prod |
|---|---|---|
| `SaleOrder.order_line` | reverso de `SaleOrderLine.order` (`sale_order_line.py:129-132`) | **29 sitios en 16 archivos** (abajo) |
| `SaleOrderLine.linked_line_ids` | reverso de `linked_line_id` (`:346-353`) | 0 |
| `SaleOrder.timesheet_ids` | reverso de `analytic.AccountAnalyticLine.order` (dueño ya BM) | 0 en prod |
| `SaleOrderLine.analytic_lines` | reverso de `AccountAnalyticLine.so_line` (dueño ya BM) | 0 |
| `SaleOrderLine.project_sale_line_maps` | reverso de `sale_timesheet.ProjectSaleLineEmployeeMap.sale_line` (dueño ya BM) | 0 |
| `CrmTeam.sale_orders` | reverso de `SaleOrder.team` (`sale_order.py:310`) | 0 |
| `CrmTag.sale_orders` | reverso de `SaleOrder.tags` (`:633`) | 0 |
| `ProductProduct.sale_order_lines`, `Uom.sale_order_lines`, `ProductComboItem.sale_order_lines`, `ProductTemplateAttributeValue.sale_order_lines_no_variant` | reversos de `SaleOrderLine.product/product_uom_id/combo_item_id/product_no_variant_attribute_value_ids` | 0 (grep `\.(sale_order_lines|sale_order_lines_no_variant)\b` → 0) |
| `AccountMoveLine.sale_line_ids` | reverso M2M de `SaleOrderLine.invoice_lines` (`:494-498`) | **1**: `addons/sale/models/account_move_line.py:30` (`.values_list('pk', flat=True)`). `addons/account_edi_ubl_cii/models/account_edi_xml_ubl_20.py:324` y `account_edi_ubl.py:2008` ya escriben `...sale_line_ids.order_id.mapped(...)` (API de recordset, hoy muerta o bloqueada; no se rompe) |
| directos (M2M) | `SaleOrder.tags`, `SaleOrder.duplicated_order_ids` (`sale_order.py:726-727,973`), `SaleOrderLine.product_no_variant_attribute_value_ids`, `SaleOrderLine.invoice_lines` | `duplicated_order_ids`: asignación en `sale_order.py:973`, sin lecturas de gestor; `tags`/`invoice_lines`: 0 usos de gestor en prod (los `.invoice_lines` de prod son todos de `addons/purchase`) |

Reversos que NO cambian porque el dueño sigue sin ser BM: `Payment.payments`, `Review.reviews`,
`StockPicking.pickings`, `ShipmentGuide.shipment_guide`, `DeliveryAddress.delivery_address`,
`SaleOrderCoupon.coupon`, `SaleOrderMatrix.matrix`, y los O2O de `sale_stock/margin/project/mrp/purchase/sms/crm/website_sale`
(medido con `_meta.get_fields()`: `owner_BM=False`). `User/Company/ShippingMethod.sale_orders` siguen gestor
(comodelo no BM). Ojo: si otra unidad adopta `stock`, `payment`, `delivery` o `rating` antes, esos reversos
cambian de tipo después.

### 3.2 Los 29 usos de gestor sobre `order_line` (prod, excluye `addons/purchase`, que tiene su propio `order_line`)

`grep -rnE "\.order_line\.(all|filter|select_related|get_or_create|create|first)\(|\(order\.order_line$"` → 29 líneas, 16 archivos:

- `addons/sale/services.py`: `:141` `get_or_create`; `:173` `.all().delete()`; `:209` `.all()`; `:247`, `:262` `.filter(pk=..).first()`; `:293` `.select_related('product').all()`; `:305` `.filter(`; `:325` `.create(` (kwargs; `BaseModel.create` recibe `vals_list`, `src/orm/models.py:865`); `:375`, `:568` `.filter(`. Además instancias: `:265` `line.delete()` y `:331` `anon_order.delete()` (borran por `Model.delete`, siguen funcionando pero `line.delete()` ya no recalcula si se porta a `unlink`; usar `line.unlink()`).
- `addons/sale/models/sale_order.py`: `:900` `.all()` (`_compute_has_archived_products`), `:1118` `.all()` (`_sum_lines`).
- `addons/sale/controllers/serializers.py:53` `.filter(`; `addons/sale/report/report_catalog.py:103` `.select_related().all()`.
- `addons/sale/data/report_templates.py:57` `<list name="items" in="docs.order_line.all">` (descriptor DTL; resuelve por `Variable(path)` en `src/addons/base/report_template.py:171-190` y un recordset no tiene `.all` → `InvalidReportTemplate`). **El descriptor está sembrado por migración** (`addons/sale/migrations/0002_seed_report_saleorder_view.py`): exige migración de datos, no sólo editar el `.py`. Además `{{ item.product.default_code|default_if_none:'' }}` (`:61`) sobre un producto nulo (ahora recordset vacío) deja de dar `None`: INFERIDO, medir.
- `addons/sale_stock/models/sale_order.py:80` `.all()`.
- `addons/sale_loyalty/services.py:58` `.all()`; `addons/sale_loyalty/models/sale_order_coupon.py:109` `.filter(`; `addons/sale_loyalty/models/sale_order.py:38` `.filter(is_reward=True).delete()` y `:65` `.filter(`.
- `addons/sale_loyalty_delivery/models/sale_order.py:53` `.filter(is_delivery=True).first()`.
- `addons/delivery/models/sale_order.py:101` `.filter(...).delete()` y `:132` `.filter(`.
- `addons/website_sale/controllers/cart.py:193`, `:488` `.select_related('product').all()`; `addons/website_sale/models/sale_order.py:488` `.all()`.
- `addons/rating/controllers/main.py:207` `.filter(product=..)`.
- `addons/payment_mercado_pago/gateway.py:65` `(order.order_line\n.filter().select_related().order_by())`; `addons/payment_paypal/gateway.py:142` `.filter().select_related().order_by()`.
- `addons/account/wizard/accrued_orders.py:223` `.filter(product__isnull=False).first()` + `:224` `if order_line is None` (el `order` puede ser de venta o de compra según el asistente; verificar cuál; con recordset `is None` deja de ser verdad).

No rompen: `.order_line.exists()` (3 sitios: `addons/account/services.py:60`, `addons/website_sale/models/sale_order.py:298`, `addons/sale/models/sale_order.py:1209`; `BaseModel.exists`, `src/orm/models.py:10919`, es falsy si vacío, y su resultado se usa sólo en booleano); `.prefetch_related('order_line')` (`addons/delivery/controllers/main.py:100`) y `.exclude(order_line=None)` (`addons/website_sale/models/sale_order.py:344`), que son lookups de queryset sobre la clase; los `SaleOrderLine.objects.*` / `SaleOrder.objects.*` (manager de clase, sin cambio): prod `SaleOrder.objects.(create|get_or_create|filter|get|all)` 3+19, `SaleOrderLine.objects.create|...` 2+4; en tests 131 + 24 y 67 + 3.

Reescritura mecánica: `.all()`/iteración → iterar el recordset; `.filter(a=b)` → `.filtered(lambda l: l.a == b)`;
`.first()` → `[:1]`/`next(iter(...), None)`; `.select_related/.order_by` → `sorted`/lectura directa; `.create(**kw)` →
`SaleOrderLine.objects.create(order=order, ...)` o `SaleOrderLine.create({...})`; `.filter(...).delete()` →
`.filtered(...).unlink()` conservando el `order._compute_amounts()` explícito (el motor de dependencias no lo dispara aquí: comentario de
`sale_order_line.py:640-659`, y `purchase_order.py:346-348` dice «este ORM no dispara @api.depends (tarea #191)»).

### 3.3 Many2one nulo → recordset vacío (los dos modelos son dueños)

Aplica a Many2one con comodelo BaseModel. En `SaleOrder`: `team` (`:310`), `journal_id` (`:518`),
`preferred_payment_method_line_id` (`:573`), `pricelist_id` (`:582`), `campaign_id`/`source_id`/`medium_id` (UtmMixin).
En `SaleOrderLine`: `product` (`:135`, nulo en secciones/notas), `product_uom_id` (`:333`), `combo_item_id` (`:381`),
`linked_line_id` (`:346`); `order` es `null=False`. Los demás (`partner` → `ResUsers`, `company`, `carrier`,
`invoice`, `partner_invoice_id`, `partner_shipping_id`, `fiscal_position_id`, `payment_term_id`, `currency_id`,
`tax_country_id`, `user_id`, `salesman_id`, `order_partner_id`, `pending_email_template_id`) siguen devolviendo `None` hasta que
su comodelo adopte BaseModel (medido arriba).

Usos fuera de los dos modelos que se rompen por `is None` sobre un FK de ese conjunto:
- `addons/sale_stock_product_expiry/models/sale_order_line.py:37` `if line.product is None: return False` (línea sin producto). **Rompe**: `line.product` vacío es un recordset, no `None`; `getattr(line.product, 'use_expiration_date', False)` quedaría como la rama alterna (probablemente `False` por valor nulo, pero cambia el camino). Reescribir `if not line.product:`.
- Los `x.product is None` de `addons/stock/*` (`stock_quant.py`, `stock_move_line.py`, `stock_orderpoint.py`, `stock_picking.py`, `stock_location.py`, `stock_storage_category.py`) son de modelos de stock, no de líneas de venta: no los toca esta unidad.
- `addons/product/models/product_product.py:651-652` (`seller.product_uom_id != uom_id`) y `addons/purchase_*` son de otros modelos.

## 4. Comparaciones `is None` / `is not None` dentro de los dos modelos

`grep -nE "is (not )?None"` sobre los dos archivos:

| Línea | Expresión | ¿Sobre un Many2one? | Veredicto |
|---|---|---|---|
| `sale_order.py:57` | `seq is None` (`IrSequence.objects.filter().first()`) | no | sin cambio |
| `sale_order.py:901` | `if line.product_id is not None` | `product_id` es el **attname** (pk crudo) de `product` | sin cambio (verificar en test que el attname sigue siendo el pk con `BaseModel`) |
| `sale_order.py:932` | `if position is not None and position.foreign_vat` (`position = self.fiscal_position_id`) | sí, FK `fiscal_position_id` a `account.AccountFiscalPosition` | sin cambio hoy (comodelo no BM → `None`); **se rompe** cuando `account` adopte `AccountFiscalPosition` (pasaría a recordset vacío): cambiar a `if position and position.foreign_vat` ya |
| `sale_order.py:1083`, `:1101` | texto de docstring / `update_fields is not None` | no | sin cambio |
| `sale_order.py:1272` | `if self.invoice_id is not None` | `invoice_id` es attname de `invoice` | sin cambio |
| `sale_order.py:1274` | `if self.company_id is None` | `company_id` es attname de `company` | sin cambio |
| `sale_order_line.py:681` | `if value is not None` en `_coerce_amount_operands` | no (escalares) | sin cambio |
| `sale_order_line.py:712` | `update_fields is not None` | no | sin cambio |

Además `sale_order.py:933-934` usa `self.company.account_fiscal_country if self.company_id else None` (guarda por attname; correcto).
No hay `is None` real sobre un Many2one de comodelo BM dentro de los dos archivos: **0**.

## 5. Tests que los consumen

Comando derivado (`test-execution-protocol`):
`grep -rlE "SaleOrder|sale\.order" tests --include=*.py | sed 's|/[^/]*$||' | sort | uniq -c | sort -k1nr`
→ **90 archivos** en 21 directorios:

```
 39 tests/integration/sale        3 tests/integration            2 tests/unit/web
  9 tests/unit/orm                3 tests/integration/mail       2 tests/unit/account_payment
  5 tests/unit/account            3 tests/unit/website_sale      2 tests/integration/delivery
  5 tests/unit/sale               2 tests/factories              2 tests/integration/loyalty
  4 tests/unit/base               2 tests/integration/base       1 bus, portal, rating (integration)
                                                                 1 tests/unit/{account_debit_note,mail,purchase_requisition,sale_timesheet}
```

Los directorios del subconjunto a ejecutar: `tests/integration/sale`, `tests/unit/sale`, `tests/unit/orm`,
`tests/unit/account`, `tests/unit/base`, `tests/integration`, `tests/integration/{mail,base,delivery,loyalty,bus,portal,rating}`,
`tests/unit/{website_sale,account_payment,web,account_debit_note,mail,purchase_requisition,sale_timesheet}`, más `tests/factories`
(no se ejecuta, pero `tests/factories/order_factory.py:35` usa `SaleOrder.objects.create`). Añadir `tests/unit/orm/test_basemodel_reach.py`
(sacar `'sale'` de `PENDING`, `:48-53`) y los directorios de `sale_stock`, `sale_loyalty`, `delivery`, `website_sale`, `payment*`, `rating`
por consumidores de producción con `order_line` (la grep de arriba sólo ve el símbolo/`sale.order` literal).

Tests con API de gestor sobre `order_line` (candidatos a romper): `grep -rnE "order_line\.(all|filter|...)\("` sobre `tests/` excluyendo purchase → **36 líneas**:
28 en `tests/integration/sale`, 4 en `tests/integration/base`, 2 en `tests/unit/account`, 2 en `tests/unit/sale`.
Altas por constructor de Django (`SaleOrder.objects.create`: 131 líneas en 40 archivos; `SaleOrderLine.objects.create`: 67 en 31) no cambian de
camino (siguen sin ejecutar `@api.constrains` ni `create` del ORM, igual que hoy). Tests sin usuario ni `su` que lean `line.order.*` / `order.order_line`
pueden recibir `PermissionDenied` por la ACL de `BaseModel` (cuántos: sólo lo mide una ejecución).

## 6. Riesgos y partición propuesta

Riesgos, por orden de daño:
1. **Borrado silencioso** de la recomputación de importes si `SaleOrderLine.delete` no se porta a `unlink` (`sale_order_line.py:724`). Sin guardia, `order.order_line` quedaría con totales viejos. Control de anulación: retirar el `unlink` y que caiga la prueba de borrado de línea y sólo ella.
2. **29 usos de gestor** en 16 archivos de 12 addons (sale, delivery, website_sale, rating, payment_mercado_pago, payment_paypal, sale_loyalty, sale_loyalty_delivery, sale_stock, account) más 36 líneas de tests. `.create(**kw)` y `.get_or_create` en `sale/services.py:141,325` no tienen equivalente directo en recordset.
3. **ACL ausente**: sin CSV de seguridad en `sale`, lecturas sin `su` se rehúsan; 13 filas de la fuente y el cableado en el manifiesto (`security/ir.model.access.csv`, y grupos `sales_team.group_sale_salesman|manager`, `account.group_account_*`, `base.group_portal` que ya existan; medir cuáles falta sembrar). Hay además una regla multiempresa sembrada por migración (`addons/sale/security/ir_rules.py`).
4. **Descriptor de reporte sembrado por migración** (`report_templates.py:57`, `migrations/0002_...`): requiere migración de datos.
5. `is None` sobre `line.product` en `sale_stock_product_expiry/models/sale_order_line.py:37`; y `position is not None` (`sale_order.py:932`) a la espera de que `account` adopte `AccountFiscalPosition`.
6. `from_db` + `_loaded_company_id` (`sale_order.py:798-801,1047-1059`) y el `save` con `update_fields`: comprobar que `BaseModel.from_db`/`write` no los saltan.
7. Reversos de dueños no BM (`stock`, `payment`, `delivery`, `rating`, y los O2O de `sale_*`) cambiarán de tipo cuando esas apps se adopten: dejar anotado en el hallazgo, no se arregla aquí.
8. La brecha de la fuente (`_unlink_except_draft_or_cancel`, `_unlink_except_confirmed`, `create` con secuencia, constrains) cambia comportamiento si se porta; fuera de la adopción.

Partición propuesta (cada una verificable por separado; el reverso `order_line` sólo se vuelve recordset cuando los DOS extremos son BM,
`src/orm/models.py:6497-6529`, así que adoptar primero la línea acota el radio):
- **U2-0, seguridad**: `addons/sale/security/ir.model.access.csv` (13 filas) + manifiesto + grupos; sin cambio de bases, sólo se vuelve efectiva al adoptar. Comprobar que `crm`/`purchase` arrancan igual.
- **U2a, `SaleOrderLine` → BaseModel** (con `SaleOrder` aún Django): bases `(models.BaseModel, AnalyticMixin, TimeStampedModel)`; `delete` → `unlink` (guarda orden y recomputa); reversos que cambian: `AccountMoveLine.sale_line_ids` (1 sitio, `account_move_line.py:30`), `analytic_lines`, `project_sale_line_maps`, `ProductProduct/Uom/ComboItem.sale_order_lines`; Many2one nulos de `product`, `product_uom_id`, `combo_item_id` (`sale_stock_product_expiry/.../sale_order_line.py:37`); `services.py:265` `line.delete()` → `line.unlink()`. Tests: `tests/unit/sale`, `tests/integration/sale`, `tests/unit/sale_timesheet`, `tests/unit/account`.
- **U2b, `SaleOrder` → BaseModel**: bases `(models.BaseModel, PortalMixin, ProductCatalogMixin, MailThread, MailActivityMixin, UtmMixin, AccountDocumentImportMixin, TimeStampedModel)`; flips `order_line` (los 29 sitios; se pueden repartir en U2b-1 `addons/sale` y U2b-2 resto de addons si el diff es grande), `linked_line_ids`, `timesheet_ids`, `CrmTeam/CrmTag.sale_orders`, `tags`, `duplicated_order_ids`; `account.fiscal_position` guarda; migración de datos del descriptor DTL; sacar `'sale'` de `PENDING` (`tests/unit/orm/test_basemodel_reach.py:48-53`, y comprobar que `test_the_pending_apps_are_exactly_the_measured_ones` sigue exacto).
- **U2c, decisión aparte**: portar `_unlink_except_draft_or_cancel`, `_unlink_except_confirmed`, `create` con secuencia, `@api.constrains`. Requiere decisión (cambia comportamiento).

*Métrica:* grep sobre `addons/ src/` (excluye `tests/`, `migrations/`, y `addons/purchase` por tener su propio `order_line`), e introspección de `_meta` tras `django.setup()` con `config.settings.testing`.
*Ciega a:* accesos dinámicos (`getattr(order, name)`, DTL de plantillas con otras rutas, serializadores DRF por `source=`), a los usos en `tests/` de variables que no se llamen `order_line`, a cuántos tests dan `PermissionDenied` (sólo una ejecución lo mide), y a `account/wizard/accrued_orders.py:223` cuyo `order` puede ser de venta o de compra (no se resolvió).
