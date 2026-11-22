<!-- Procedencia: subagente de investigación de sólo lectura (2026-11-22), nivel 3 de retención. Verificado de forma independiente por la sesión: ausencia de addons/stock/security y de data en el manifiesto, y las firmas write(self, **vals)/write(cls, ...)/unlink(cls, ...) en product_strategy.py:364, stock_location.py:587,1096, stock_move_line.py:1184,1369, stock_package.py:645, stock_package_type.py:369, stock_quant.py:898, stock_warehouse.py:666,822. El resto de cifras no se ha re-medido. -->

<!-- Informe de un subagente de investigación (nivel 3 al recibirlo): solo lectura sobre /home/user/kaupamex-api. -->

# Investigación de solo lectura — `stock` hacia `models.BaseModel`

Árbol: `/home/user/kaupamex-api` (sólo lectura). Referencia: `odoo19c`, `$O` =
`/home/user/odoo-tools/19.x/odoo-19.0/odoo-19.0/odoo-19.0` (sólo lectura). Precedente leído:
`scripts/workbench/orm-continuation-plan-20261103T095630/outputs/sale-basemodel-adoption-research.md`
y `designs/sale-basemodel-u3a-order-line.md`, `sale-security-acl.md`. Las mediciones de modelos salieron de
`django.setup()` con `DJANGO_SETTINGS_MODULE=config.settings.testing` e introspección de `_meta` (sin pytest,
sin migraciones, sin conexión a la base). Los scripts viven en el scratchpad
(`introspect.py`, `acc.py`, `graph.py`); la salida cruda en `intro.txt`, `acc.txt`, `graph.txt`.
No existe `src/addons/stock` (`ls src/addons/stock` → *No such file*); todo `stock` está en `addons/stock/`.

## 1. Clases con `_name` fuera de `BaseModel`

Medido como lo mide `tests/unit/orm/test_basemodel_reach.py:33-44` (`model.__dict__.get('_name')`, sin
abstractos ni proxies): `apps.get_app_config('stock').get_models()` → **28 modelos concretos, 20 con `_name`
propio, 20 fuera de `BaseModel`** (`awk -F'|' '$2!="None"{n++; if($3=="BM=False")o++}' intro.txt` → `named 20 outside 20`).
`stock` está en `PENDING` (`test_basemodel_reach.py:48-53`).

| `_name` | Clase | Bases directas | Archivo |
|---|---|---|---|
| `stock.storage.category` | `StockStorageCategory` | `TimeStampedModel` | `stock_storage_category.py:114` |
| `stock.storage.category.capacity` | `StockStorageCategoryCapacity` | `TimeStampedModel` | `stock_storage_category.py:206` |
| `stock.package.type` | `StockPackageType` | `DefaultGetMixin, TimeStampedModel` | `stock_package_type.py:108` |
| `product.removal` | `ProductRemoval` | `TimeStampedModel` | `product_strategy.py:124` |
| `stock.putaway.rule` | `StockPutawayRule` | `DefaultGetMixin, TimeStampedModel` | `product_strategy.py:170` |
| `stock.package` | `StockPackage` | `DefaultGetMixin, TimeStampedModel` | `stock_package.py:198` |
| `stock.package.history` | `StockPackageHistory` | `TimeStampedModel` | `stock_package_history.py:66` |
| `stock.lot` | `StockLot` | `MailThread, MailActivityMixin, TimeStampedModel` | `stock_lot.py:244` |
| `stock.quant` | `StockQuant` | `DefaultGetMixin, TimeStampedModel` | `stock_quant.py:360` |
| `stock.move.line` | `StockMoveLine` | `TimeStampedModel` | `stock_move_line.py:318` |
| `stock.rule` | `StockRule` | `TimeStampedModel` | `stock_rule.py:414` |
| `stock.move` | `StockMove` | `DefaultGetMixin, TimeStampedModel` | `stock_move.py:378` |
| `stock.reference` | `StockReference` | `TimeStampedModel` | `stock_reference.py:64` |
| `stock.picking.type` | `StockPickingType` | `DefaultGetMixin, TimeStampedModel` | `stock_picking.py:224` |
| `stock.picking` | `StockPicking` | `MailThread, MailActivityMixin, DefaultGetMixin, TimeStampedModel` (+1 base en la línea siguiente) | `stock_picking.py:1027` |
| `stock.warehouse` | `StockWarehouse` | `TimeStampedModel` | `stock_warehouse.py:298` |
| `stock.scrap` | `StockScrap` | `MailThread, TimeStampedModel` | `stock_scrap.py:163` |
| `stock.scrap.reason.tag` | `StockScrapReasonTag` | `TimeStampedModel` | `stock_scrap.py:584` |
| `stock.warehouse.orderpoint` | `StockWarehouseOrderpoint` | `TimeStampedModel` | `stock_orderpoint.py:270` |
| `return.request` | `ReturnRequest` | `MailThread, TimeStampedModel, SoftDeleteModel` | `return_request.py:22` |

Los 8 modelos concretos **sin** `_name` propio (no entran en la medición): `StockLocation` (`stock_location.py:195`)
y `StockRoute` (`:992`) —los dos son contrapartes de la fuente (`stock.location`, `stock.route`) y **no declaran
la cabecera**—, más las tablas intermedias `StockMoveLineConsumeRel`, `PickingTypeFavoriteUserRel`,
`StockWarehouseResupply` (`RecordLoaderMixin, Model`) y los hijos de `return.request`
(`ReturnItem`, `ReturnHistoryEntry`, `ReturnEvidence`). `grep -nE "_name\b *=" addons/stock/models/stock_location.py`
sólo da `complete_name`/`related_name`: ninguna cabecera. Quien adopte `StockLocation`/`StockRoute` debe portarles
primero `_name`/`_description` (regla `atributos-de-clase-de-modelo`), y sólo entonces entran en el trinquete.

Otros hechos de las bases (medidos con `grep` y `orm.models`):
- `BaseModel` **ya hereda** `DefaultGetMixin` (`src/orm/models.py:6921`: `class BaseModel(DefaultGetMixin, RecordLoaderMixin, OrderMixin, Model)`).
  Siete clases listan además `models.DefaultGetMixin` (`StockPackageType`, `StockPutawayRule`, `StockPackage`,
  `StockQuant`, `StockMove`, `StockPickingType`, `StockPicking`; `StockLocation` también, sin `_name`). Con
  `(models.BaseModel, models.DefaultGetMixin, …)` el MRO es consistente, pero con el orden inverso falla; lo
  correcto es retirar la mención redundante.
- Mixins ya adoptados en otros modelos `BaseModel`: `MailThread`, `MailActivityMixin` (`PurchaseOrder`,
  `addons/purchase/models/purchase_order.py:122-124`) y `TimeStampedModel` (abstracto). No hay padre que marcar.
- `SoftDeleteModel` (`src/addons/base/models/soft_delete_mixin.py:73`, `delete()` en `:108`) en `ReturnRequest` **no
  tiene precedente adoptado**: `ContactMessage` (`addons/crm/models/contact_message.py:19`) lo usa pero
  `PENDING` no lo marca como adoptado y su clase no antepone `BaseModel`. `BaseModel.unlink`
  (`src/orm/models.py:9098`) hace `QuerySet.delete` directo y **no** pasa por el borrado lógico.

## 2. Usos de API de gestor que cambian

Regla (`src/orm/models.py:6470` `_x2many_descriptor_get`, `:6690-6733` `_forward_get`): un x2many es recordset sólo si
dueño **y** comodelo son `BaseModel`; un Many2one nulo es recordset vacío sólo si quien lee y el comodelo son
`BaseModel`. Al adoptar un conjunto S cambian todas las relaciones con ambos extremos en `BM ∪ S`.

Accesores x2many de los 20 modelos (propios y reversos, de cualquier app): `acc.py` → **79 filas, 62 nombres**
(`wc -l acc.txt`; `cut -d'|' -f1 acc.txt | sort -u | wc -l`).

Búsqueda: `rg -n "\.(<62 nombres>)\.(all|filter|exclude|first|last|count|create|exists|order_by|delete|get|values_list|values|select_related|prefetch_related|update|aggregate|annotate|add|remove|set|clear)\(" addons src tests --glob '*.py'`.

- **Producción: 180 ocurrencias en 23 archivos** (`rg -o -N --no-filename … addons src | wc -l`; `rg -l … | wc -l`).
- **Pruebas: 51 ocurrencias en 11 archivos** (mismo patrón sobre `tests/`).
- Multilínea (`.nombre` al final de línea y `.método(` en la siguiente): **0** (`rg -U`); 5 líneas con `.nombre` al final, todas asignaciones sin método (p. ej. `stock_package.py:721,773`).

Producción por accesor (conteo de ocurrencias): `move_line_ids` 31 · `move_ids` 27 · `route_ids` 22 · `move_dest_ids` 20 ·
`move_orig_ids` 19 · `reference_ids` 10 · `quant_ids` 9 · `rule_ids` 8 · `package_type_ids` 5 ·
`created_purchase_line_ids` 5 · `favorite_user_ids` 4 · `resupply_wh_ids` 3 · `quants` 3 · `child_package_ids` 3 ·
`capacity_ids` 3 · `return_ids` 2 · una cada una `uom_ids`, `putaway_rule_ids`, `pickings`, `package_ids`,
`package_history_ids`, `child_package_dest_ids`.
Pruebas: `move_line_ids` 11 · `categ_ids` 9 · `move_dest_ids` 8 · `move_orig_ids` 5 · `reference_ids` 4 · `pickings` 4 ·
`picking_ids` 2 · `move_ids` 2 · una cada una `stock_moves`, `route_ids`, `return_ids`, `package_type_ids`,
`package_history_ids`, `backorder_ids`.

Por archivo (producción; `rg -c` sobre las coincidencias de la primera búsqueda, que usa los 23 métodos sin `add/remove/set/clear`: 182 líneas):

| Archivo | Líneas |
|---|---|
| `addons/stock/models/stock_move.py` | 40 |
| `addons/stock/models/stock_picking.py` | 34 |
| `addons/stock/models/stock_rule.py` | 11 |
| `addons/stock/models/stock_package.py` | 10 |
| `addons/purchase_stock/models/purchase_order_line.py` | 10 |
| `addons/stock/models/stock_warehouse.py` | 8 |
| `addons/stock/models/stock_location.py` | 8 |
| `addons/stock/models/stock_lot.py` | 7 |
| `addons/stock/models/product.py` | 6 |
| `addons/stock/models/stock_scrap.py`, `purchase_stock/models/stock_rule.py`, `purchase_stock/models/stock_move.py`, `stock_move_line.py`, `product_strategy.py` | 3 cada uno |
| `stock_storage_category.py`, `purchase_stock/models/stock.py` | 2 cada uno |
| `stock_replenish_mixin.py`, `stock_reference.py`, `stock_package_type.py`, `purchase_stock/models/{stock_replenish_mixin,product}.py`, `project_stock/models/project_project.py` | 1 cada uno |

Pruebas: `tests/unit/stock/test_stock_move_lots.py` 7 · `tests/unit/stock/test_stock_picking.py` 6 ·
`tests/unit/stock/test_stock_picking_packages.py` 4 · `tests/integration/sale/test_sale_order_v5a.py` 4 ·
`tests/integration/stock/test_stock_orderpoint.py` 1 · `tests/integration/sale/test_stock_product_surface.py` 1 (los `.categ_ids.add` están en esos archivos de `tests/integration/sale`).
Métodos (producción, `rg -o -N --no-filename … -r '$2' addons src | sort | uniq -c`): `.all()` 98 · `.exists()` 17 · `.values_list()` 14 · `.filter()` 12 · `.add()` 11 · `.exclude()` 6 · `.remove()` 5 · `.count()` 5 · `.update()` 4 · `.first()` 3 · `.set()` 2 · `.order_by()` 1 · `.clear()` 1 · `.aggregate()` 1 · `.create()` 0 (suma 180). Pruebas: `.add()` 28 · `.all()` 13 · `.count()` 3 · `.get()` 2 · `.filter()` 2 · `.values_list()` 1 · `.exists()` 1 · `.create()` 1 (suma 51).

Hallazgos concretos de forma, no sólo de nombre:
- Hay borrados masivos sobre reversos: `self.move_line_ids.all().delete()` (`stock_move.py:1360`),
  `self.move_line_ids.filter(package_id__in=…).delete()` (`stock_picking.py:2412`). Con recordset hay que usar `.unlink()`.
- `rule_ids.update(…)` (`stock_warehouse.py`, 1) y `capacity_ids.set(…)` (`stock_storage_category.py`, 1): `update`/`set` de gestor
  no existen en recordset (el `write`/asignación sí).
- Los reversos hacia modelos aún no adoptados fuera de `stock` **no** cambian hasta que éstos se adopten:
  `StockValuationLayer.stock_move_id`, `StockValuationAdjustment.move`, `MrpProductionMove.move` (todos `nonBM`,
  `graph.py`), por eso `valuation_layers` y `landed_cost_adjustments` siguen siendo gestor.
- Reversos que cambian por modelos **ya** `BaseModel` fuera de `stock`: `PurchaseOrder.picking_type` →
  `StockPickingType.purchase_orders`, `PurchaseOrderLine.orderpoint` → `StockWarehouseOrderpoint.purchase_line_ids`,
  `PurchaseOrderLine.location_final` (hacia `StockLocation`, sin `_name`), `Uom.package_type` →
  `StockPackageType.uom_ids`, `ProductCategory.removal_strategy` → `ProductRemoval.categ_ids` (`graph.py`, sección *external BM owners*).
- Many2one nulos: **146** comparaciones `is None`/`is not None` sobre FKs hacia modelos de `stock`
  (`rg -n "\.(picking|picking_type|location|location_dest|location_src|lot|package|result_package|scrap|warehouse|rule|route|orderpoint|move|package_type|storage_category|removal_strategy)\s+is\s+(not\s+)?None"`): 134 en `addons/stock`
  (58 `stock_move_line.py`, 30 `stock_quant.py`, 22 `stock_picking.py`, 8 `stock_orderpoint.py`), 8 en `purchase_stock`, 4 en `product_expiry`.
  Además 20 sobre `product/product_uom/purchase_line` (`rg … | awk` total 20) cuyo comodelo **ya** es `BaseModel`: esas flipan al adoptar el dueño,
  no el comodelo (`StockMove→ProductProduct/Uom/PurchaseOrderLine`, `StockMoveLine→ProductProduct/Uom`, `StockLot→ProductProduct`).
  Sólo cuentan las FKs cuyo comodelo es `BaseModel` en ese momento; las que apuntan a `StockLocation`/`StockRoute` no flipan hasta adoptarlos.
- Modelos de referencia afuera que citan clases de `stock` (para el radio de las pruebas): 41 archivos de producción fuera de `addons/stock/`
  (`purchase_stock` 10, `product_expiry` 7, `stock_account` 5, `project_stock` 4, `mrp` 4, `stock_landed_costs` 2, `mrp_subcontracting` 2, `sale` 1, `product` 1, `orm` 1, otros 4)
  y 49 archivos de `tests/` (16 `tests/unit/stock` + 10 `tests/integration/stock` son los directos).

## 3. `delete()`, `save()` y compañía

Sobreescritos en los 20 modelos (`grep -nE "def (save|delete|create|write|unlink|from_db)\("` por clase):

| Clase | `save` | `delete`/`unlink` | `create` | `write` |
|---|---|---|---|---|
| `StockLot` | `stock_lot.py:638` (corre `@api.constrains`) | — | — | — |
| `StockMove` | `:1205` | `unlink` `:1348` + `delete = unlink` `:1366` | `:1289` | `:1308` (`write(self, vals, skip_uom_conversion=False)`) |
| `StockMoveLine` | `:758` (constraints) | `unlink(cls, lines)` `:1369` (**classmethod**) | `:1067` | `write(cls, lines, vals)` `:1184` (**classmethod**) |
| `StockOrderpoint` | `:994` | — | — | — |
| `StockPackage` | `:363` | — | `:620` | `write(self, **vals)` `:645` |
| `StockPackageType` | — | — | `:343` | `write(self, **vals)` `:369` |
| `StockPickingType` | `:772` | — | `:442` | `write(self, vals)` `:496` |
| `StockPicking` | `:1461` | `unlink` `:1573` + `delete = unlink` `:1611` | `:1500` | `:1522` |
| `StockQuant` | `:699` | — | `:767` | `write(self, **vals)` `:898` |
| `StockRule` | `:652` | — | — | — |
| `StockScrap` | `:409` | **`delete`** `:375` (aplica `_unlink_except_done`, luego `super().delete`) | — | — |
| `StockWarehouse` | `:601` | `unlink(cls, warehouses)` `:822` (**classmethod**) | `:540` | `write(cls, warehouses, vals)` `:666` (**classmethod**) |
| `StockPutawayRule` | — | — | `:345` | `write(self, **vals)` `:364` |

(Sin `_name`, fuera de este recuento: `StockLocation` `save:557 create:539 write:587 unlink:647`, `StockRoute` `write:1096`.)

Qué cambia con `BaseModel` (`BaseModel.unlink(self)` `src/orm/models.py:9098`: ACL de borrado, vuelca lo pendiente, `QuerySet.delete`;
`BaseModel.write(self, vals)` `:10628`; `BaseModel.create(cls, vals_list)` `:866`):
1. **Las firmas heredadas no coinciden con las de `BaseModel`.** `write(self, **vals)` (6 clases), `write(cls, lines, vals)`
   (`StockMoveLine`, `StockWarehouse`) y `unlink(cls, lines)`/`unlink(cls, warehouses)` son corrimientos de un ORM previo y
   **sombrean** a `BaseModel.write`/`unlink`: se saltan la ACL, el `modified` y el flush del ORM, y `rec.write({...})` o
   `lines.unlink()` sobre un recordset no llegan a ellas con el contrato esperado. Es la decisión de mayor tamaño de la adopción: **5 `write`
   con `**vals`/`(cls, lines, vals)` y 3 `unlink` classmethod** hay que reconciliarlos con la fuente, no sólo marcar la base.
   Precedente adoptado con `save`/`create`/`delete` propios: `PurchaseOrder.save`/`create` (`purchase_order.py:346,445`), `CrmLead.delete` (`crm_lead.py:1715`).
2. **`delete()` de Django salta `unlink`.** `StockScrap.delete` (`:375`) es el gancho de la guarda; `StockMove` y `StockPicking`
   fijan `delete = unlink` (`stock_move.py:1366`, `stock_picking.py:1611`) para que ambos nombres coincidan. En un recordset
   `BaseModel` `unlink` es el nombre canónico y la guarda `@api.ondelete` se ejecuta en el `Collector` (`_run_ondelete_checks`,
   `src/orm/models.py:6179`; decorador `src/orm/decorators.py:174`). Los sitios que borran por instancia —`ml.delete()` `stock_move.py:1989`,
   `move.delete()` `:2173` y `stock_picking.py:1608`, `linea.delete()` `stock_move.py:2656`— pasan a `unlink()`; los bulk
   `QuerySet.delete()` (`stock_package.py:802,805`, `stock_quant.py:1884`, `stock_orderpoint.py:1138,1608`, `stock_move_line.py:1395`, `stock_warehouse.py:824`)
   ya no pasan por ninguna guarda y no cambian. En total `rg "\.delete\(\)"` da 21 en `stock`, `purchase_stock`, `mrp*`, `stock_*`, `product_expiry`, `project_stock`, `sale_stock`.
3. **`ReturnRequest`** (`SoftDeleteModel`): su borrado lógico vive en `delete()`; `BaseModel.unlink` lo salta (`QuerySet.delete`). Sin precedente.
4. **Fuente Odoo.** `@api.ondelete(at_uninstall=False)` en `$O/addons/stock/models/`: `stock_move.py:2332` (`_unlink_if_draft_or_cancel`),
   `stock_scrap.py:120`, `stock_location.py:201`, `stock_move_line.py:557`, `stock_quant.py:362`. `unlink` propio en la fuente:
   `stock_move.py:2337`, `stock_picking.py:1170`, `stock_location.py:266`, `stock_warehouse.py:317`, `stock_move_line.py:567`.
   `write`/`create` propios en la fuente: `stock_move.py:819,833`, `stock_picking.py:1117,1139`, `stock_lot.py:182,187`,
   `stock_warehouse.py:114,186`, `stock_move_line.py:341,424`, `stock_quant.py:253,351`, `stock_package.py:278,289`,
   `stock_orderpoint.py:295,300`, `stock_package_type.py:94,105`, `product_strategy.py:103,107`. Es decir, **la fuente sí tiene** equivalentes de
   cada uno de los overrides locales de `create`/`write`; la diferencia es que el stack local los expresa con la forma de
   Django (`save`, `delete = unlink`, `**vals`), así que la adopción es de contrato, no de comportamiento nuevo.

## 4. `prefetch_related`, `select_related`, `annotate`

- **`prefetch_related` sobre reversos de estos modelos: 0** (`rg "prefetch_related\(" addons src tests` con filtro `stock|picking|quant` no devuelve línea en
  `addons/stock`, `purchase_stock`, `sale_stock`, `product_expiry`, `project_stock`; el único comentario es `stock_move.py:1596` que lo menciona en prosa).
  Con la cuenta global de `prefetch_related` (otros addons) no aplica a `stock`.
- **`select_related`: 16 en `addons/stock`** (`rg "select_related\(" addons/stock | wc -l`); cadenas como
  `self.contained_quant_ids.select_related('product','product_uom')` (`stock_package.py:436`), `self.all_children_package_ids.select_related(…)` (`:869,872,879,885`),
  `stock_picking.py:2554`, `stock_orderpoint.py:485,1198`, `stock_location.py:416`, `product.py:653`, `controllers/main.py:91`. Son `QuerySet` de Django sobre
  `Model.objects`, no sobre un reverso `BaseModel`; no se rompen por la adopción en sí, pero `select_related` sobre un FK cuyo extremo pasa a `BaseModel`
  conserva su `JOIN` y devuelve el objeto de Django.
- **`annotate`: 30 en `addons/stock`** (`rg "\.annotate\(" addons/stock | wc -l`): `stock_quant.py` 8, `stock_location.py` 7, `stock_orderpoint.py` 5, `product.py` 5,
  `stock_picking.py:607`, `stock_warehouse.py:838`, `stock_lot.py:744`, `stock_rule.py` 1, `controllers/main.py:37` 1. Casi todos son
  `values(...).annotate(...)` de agregados escalares (consulta de Django, no sobre una instancia): siguen válidos. El rechazo ocurre en
  `BaseModel.__setattr__` (`src/orm/models.py:7012-7020`) cuando Django intenta **asignar el valor anotado sobre un registro** (`annotate()` y `Prefetch(to_attr=…)`):
  hay que auditar los que **iteran instancias** (`stock_picking.py:607` `queryset.annotate(…)` devuelve filas; `controllers/main.py:37` `StockQuant.objects.annotate(…)`).
  Con esta medición no se puede decir cuántos de los 30 iteran instancias: es un `DESCONOCIDO` con condición de cierre —correr el subconjunto rojo de la unidad.
- Reversos con consulta por nombre de relación (`StockMove.objects.filter(move_line_ids__…)`) usan lookups de Django y no cambian.

## 5. ACL

- **`addons/stock/security/` no existe** (`ls addons/stock/security` → *No such file*). El manifiesto **no declara** `data`
  (`grep -nE "security|csv|access|data" addons/stock/__manifest__.py` sólo devuelve prosa). La fuente trae
  `$O/addons/stock/security/ir.model.access.csv` (77 filas de datos, `wc -l` = 78 con cabecera) y `stock_security.xml` (169 líneas),
  y su manifiesto los carga (`$O/addons/stock/__manifest__.py:20-21`).
- Filas de la fuente para los modelos de este recuento: **38 filas** para 19 de los 20 (todos menos `return.request`, que es propio del L0, sin fuente)
  más **5** para `stock.location` (3) y `stock.route` (2). Cuenta por modelo (python `csv` sobre el CSV): `stock.warehouse` 2, `stock.picking` 2,
  `stock.picking.type` 3, `stock.lot` 1, `stock.move` 2, `stock.warehouse.orderpoint` 2, `stock.quant` 2, `stock.package` 3, `stock.rule` 3,
  `stock.move.line` 3, `stock.putaway.rule` 2, `product.removal` 1, `stock.scrap` 2, `stock.scrap.reason.tag` 2, `stock.package.type` 2,
  `stock.storage.category` 2, `stock.storage.category.capacity` 2, `stock.package.history` 1, `stock.reference` 1 (id `access_stock_reference`,
  `base.group_user`, 1/1/1/0).
- **Grupos que esas filas usan: `base.group_user`, `base.group_partner_manager`, `stock.group_stock_user`, `stock.group_stock_manager`.**
  Los dos últimos **no existen como datos en este árbol**: `rg "group_stock_user|group_stock_manager" addons` sólo encuentra consumidores
  (`stock_warehouse.py:523` `_user_has_group(user, 'stock.group_stock_manager')`, `stock_picking.py:1382`, `authz/management/commands/seed_menu.py:43`) y ninguna definición.
  La fuente los define en `$O/addons/stock/security/stock_security.xml:10-20` (`group_stock_user`, `group_stock_manager`, `privilege_id` `res_groups_privilege_inventory`),
  más `group_stock_multi_locations`/`multi_warehouses` (`:26,30`) y `group_tracking_lot`/`owner` (`:46,54`). **A diferencia de `sale` (donde los cinco grupos ya existían),
  aquí el CSV no se puede portar solo: falta primero el XML de grupos.** Precedente: `addons/purchase/security/purchase_security.xml` (grupo + privilegio) y `ir.model.access.csv`
  (`addons/purchase/__manifest__.py:39-40`).
- `return.request` no tiene fila en la fuente: su ACL es decisión de diseño (recomendación: replicar la de `stock.picking`, con `stock.group_stock_user`/`manager`).
- Los gates de capacidad de vistas (`addons/stock/authz_catalog.py`) son otro mecanismo (DRF) y no sustituyen la ACL del ORM.

## 6. Partición propuesta (en orden de dependencia)

Criterio: un reverso/Many2one sólo cambia de tipo cuando **ambos extremos** son `BaseModel`; por tanto la carga de cada unidad cae
en las relaciones que cierra. Se adopta en el orden de la condensación de la gráfica de FK (`graph.py`, Tarjan sobre owner→target;
destinos primero): los nodos hoja y poco referenciados abren; los ejes `StockMove`/`StockMoveLine`/`StockPicking`, que concentran 27 + 31 + 39
de los 180 usos de producción, cierran. Hay **un ciclo real**: `StockWarehouse ↔ StockPickingType ↔ StockRule` (ejes `warehouse`, `picking_type`, `rule`, `route`),
que debe ir en una sola unidad. Se sigue la lección de `sale` (cada unidad deja la anterior verde antes de abrir la siguiente).

| Unidad | Contenido | Por qué en este orden | Cambio de tipo que concentra |
|---|---|---|---|
| **U0-0 — grupos + ACL** | `security/stock_security.xml` (grupos `stock.group_stock_user/manager` con privilegio, y los ocultos que consuman las reglas), `security/ir.model.access.csv` (38 filas + decisión de `return.request`; las 5 de `StockLocation`/`StockRoute` quedan declaradas hasta su unidad), manifiesto con `'data'` | No existe ningún grupo de `stock`; sin la ACL un `BaseModel` rehúsa lecturas a quien no sea `su` (precedente `sale-security-acl.md`, `account.move`) | ninguna de tipo; sólo permisos |
| **U1 — catálogos hoja** | `StockStorageCategory`, `StockStorageCategoryCapacity`, `StockPackageType`, `ProductRemoval`, `StockPutawayRule`, `StockScrapReasonTag` | Sin FK de ellos hacia el resto de los 20 salvo entre sí; pocos usos: `capacity_ids` 3, `putaway_rule_ids` 1, `package_type_ids` 5 (prod); `Uom.package_type`→`uom_ids` y `ProductCategory.removal_strategy`→`categ_ids` flipan aquí (9 `.categ_ids.add` en tests a confirmar). Retirar `DefaultGetMixin` redundante en `StockPackageType`/`StockPutawayRule` | `capacity_ids`, `putaway_rule_ids`, `uom_ids`, `categ_ids` |
| **U2 — paquetes, lotes, quants** | `StockPackage`, `StockPackageHistory`, `StockLot`, `StockQuant` | Sólo apuntan a `StockLocation` (sin `_name`) y entre sí; `StockLot` es el único con `MailThread/MailActivityMixin` (precedente `PurchaseOrder`). `write(self, **vals)` de `StockPackage` y `StockQuant` y los `save` con `@api.constrains` se concilian aquí | `quant_ids`, `quants`, `child_package_ids`, `package_history_ids`, `history_ids` (≈14 usos prod); 7+3+4+2 `is None` hacia `lot`/`package` |
| **U3 — estructura (ciclo)** | `StockWarehouse`, `StockPickingType`, `StockRule`, `StockWarehouseOrderpoint` | Ciclo `Warehouse↔PickingType↔Rule`: una sola unidad. `Orderpoint` se arrastra porque su FK a `warehouse` y `route` cierra al adoptar el ciclo y `StockMove` lo referencia. `write(cls, warehouses, vals)`, `unlink(cls, warehouses)` y `route_ids` (22 usos prod; incluye `product.route_ids`: verificar propietario) son el grueso | `rule_ids`, `route_ids`, `resupply_wh_ids`, `purchase_orders` (BM externo), `purchase_line_ids` (BM externo) |
| **U4a — línea de movimiento** | `StockMoveLine` | Dueño de FK hacia `move`, `picking`, `lot`, `package`, `package_history` (**el nodo hoja de la condensación**: nadie lo referencia con FK salvo la tabla intermedia sin `_name`); como la línea de venta, se adopta antes del padre para no mover `move_line_ids` todavía. Reconciliar `write(cls, lines, vals)` y `unlink(cls, lines)` | 58 `is None` de `stock_move_line.py` |
| **U4b — movimiento y referencia** | `StockMove`, `StockReference` | `Move↔MoveLine` y `Move↔Reference` (M2M `reference_ids`): al adoptar `StockMove` se cierran `move_line_ids` (31 prod / 11 tests) y `move_dest_ids`/`move_orig_ids` (39 prod / 13 tests medidos, incluye `.add` de M2M). `delete = unlink` y `_unlink_if_draft_or_cancel` (`@api.ondelete` en la fuente) aquí | `move_line_ids`, `move_dest_ids`, `move_orig_ids`, `reference_ids`, `stock_moves`, `returned_move_ids` |
| **U4c — albarán y desecho** | `StockScrap`, `StockPicking` | Padres de `Move.scrap`/`Move.picking`; `StockPicking` es el que más `.all()` (`move_ids` 27) concentra; `StockScrap.delete` → `unlink`; `StockPicking.unlink` en dos fases (`stock_picking.py:1573-1611`). Requiere U4b para que `move_ids` sea recordset | `move_ids`, `backorder_ids`, `return_ids`, `scraps`, `pickings`, `picking_ids` |
| **U5 — `return.request` (aparte)** | `ReturnRequest` y sus hijos si se les da `_name` | Modelo propio del L0 sin fuente ni ACL de la fuente; `SoftDeleteModel` exige decidir cómo convive el borrado lógico con `BaseModel.unlink`. Independiente del resto; puede ir en cualquier momento tras U0-0 | `items`, `history_entries`, `evidence` (los hijos no tienen `_name`: seguirían gestor) |
| **U6 — `StockLocation` y `StockRoute`** | portar `_name`/`_description` y las filas ACL de la fuente (5) y luego adoptar | Son el eje de la gráfica (12 modelos los referencian) pero **no cuentan en el trinquete**; adoptarlos al final evita mezclar 12 FK nulos con las otras unidades. No sacan `stock` de `PENDING` por sí solos; sacan `stock` del trinquete las U1–U5 + (si se desea) U6 | `child_ids`, `quants`, `move_line_ids`(dest), `moves_in/out`, `rules_in/out`, `putaway_rule_ids`, `route_ids`; `PurchaseOrderLine.location_final` |

`stock` sale de `PENDING` cuando U1–U5 están hechas (los 20 modelos con `_name`); U6 es deuda separada porque `StockLocation`/`StockRoute` no
declaran `_name` y el trinquete sólo mide lo que lo declara.

Reconciliación transversal, que no cabe en ninguna unidad aislada: los `create`/`write`/`unlink` con la forma de un ORM previo
(sección 3) ya existen en cada eje; conviene decidir **una sola** regla (por ejemplo, retirar `**vals` y `classmethod` en favor de la firma de
`BaseModel`) antes de U2, y aplicarla en cada unidad.

Alternativa evaluada y descartada: adoptar los 20 modelos de golpe. Descartada porque la sola `rg` de la sección 2 da 180 usos de
gestor en 23 archivos de producción y 51 en 11 de pruebas (más 146 `is None`), y un subconjunto rojo de esa extensión no atribuye causa
(`alcance-de-la-suite.md`).

*Métrica:* clases por `django.setup()` + `_meta` (20 con `_name` fuera de `BaseModel`, 28 modelos concretos); usos de gestor por `rg` con el patrón
`.<accesor>.<método>(` sobre 62 nombres derivados de `_meta.get_fields()`; `delete/save/write/create/unlink` y `@api.ondelete` por `grep -nE "def …"`;
ACL por `ls`, `grep` sobre el manifiesto y `csv.DictReader` sobre la fuente.
*Ciega a:* un accesor con el mismo nombre en otro modelo (`route_ids` también vive en `product.template`, `move_ids` en otros dueños; ningún conteo atribuye el
propietario de cada línea); un reverso usado a través de variable local (`m = self.move_line_ids; m.filter(…)`); el estilo `getattr(obj, 'move_line_ids')`;
`values(...).annotate(...)` que iteran instancias (30 `annotate`, no se pudo distinguir cuántos); cualquier uso en plantillas DTL de informe (`<list in="docs.order_line.all">`
en `sale` fue una forma así; **no** se barrió `addons/stock/data/*.py` ni los informes de stock); el comportamiento en ejecución de los `write(cls, lines, vals)` y el costo real
en pruebas, que sólo una ejecución del subconjunto rojo mide.
