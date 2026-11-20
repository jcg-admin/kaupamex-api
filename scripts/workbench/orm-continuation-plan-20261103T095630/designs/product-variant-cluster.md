# El grupo de variantes de `product`: cuatro modelos que se llaman entre sí

Creado: 2026-11-20T15:36:39 (UTC). TASK-API-0122. Sucede a
`product-attribute-value-complete.md`, cuyo módulo declara la divergencia
de mecanismo que este grupo retira.

## Medido (`odoo19c: addons/product/models/`)

| Modelo | Fuente | Puerto | Falta |
|---|---|---|---|
| `product.template.attribute.line` | 284 líneas | 78 | `active`, `value_count`, `product_template_value_ids` declarado y diez métodos (`create`, `write`, `unlink`, `_update_product_template_attribute_values`, …) |
| `product.template.attribute.value` | 198 líneas | ~90 | once campos y doce métodos (`_check_valid_values`, `_get_combination_name`, …) |
| `product.template.attribute.exclusion` | 47 líneas | — | el modelo entero y sus dos filas de ACL |
| `product.template` (variantes) | `product_template.py:770-1400` | `addons/product/services.py` (100 líneas) | `_create_variant_ids` y once ayudantes como métodos del modelo |

Los cuatro son `TimeStampedModel`. La fuente está escrita sobre
recordsets (`filtered`, `mapped`, `with_context(active_test=False)`,
`_without_no_variant_attributes`): portar un modelo sin los otros obliga a
traducir cada llamada al manager de Django, que es la divergencia que ya
declara `product_attribute_value.py`.

`create`/`write`/`unlink` de la línea llaman
`product_tmpl_id._create_variant_ids()` y
`_update_product_template_attribute_values`; la exclusión llama
`_create_variant_ids`; PTAV llama `_get_combination_name` desde
`product.product`. No hay una pieza que cierre sola.

## Etapas

1. `basemodel-adoption-product-variant-cluster-0397`: los cuatro modelos
   (`product.template`, `product.product`, PTAL, PTAV) sobre
   `BaseModel`, sin cambio de conducta; se retiran las traducciones a
   manager de `product_attribute_value.py`. Precedente
   `designs/basemodel-adoption-uom.md`: medir antes qué consumidores leen
   con la ACL del usuario (los directorios de prueba de `sale`, `stock`,
   `purchase`, `mrp` corren hoy sin usuario).
2. `ptal-complete-0122`: campos y métodos de la línea, con
   `_update_product_template_attribute_values` en lugar de
   `services.sync_template_values`.
3. `product-template-attribute-exclusion-0122`: el modelo y sus dos filas.
4. `ptav-complete-0122`: campos y métodos de PTAV, `product_tmpl_id` y
   `attribute_id` almacenados.
5. `product-template-create-variant-ids-0122`: `_create_variant_ids` y
   sus ayudantes; `services.combinations` y sus consumidores pasan a los
   métodos.

Consumidores actuales de `addons/product/services.py` (grep, 2026-11-20T15:36:39):

          5 addons/product/services.py
          6 tests/integration/product/test_product_variants_and_stock.py
         14 tests/integration/sale/test_product_attribute.py
          2 tests/integration/test_orm/test_domain.py
          1 tests/unit/orm/test_contract_domains_reference.py
          1 tests/unit/tools/test_set_expression_against_the_reference.py

## Etapa 1 medida (2026-11-20, suite entera sobre `76067059` + el cambio de base)

Con los cuatro modelos sobre `BaseModel` y nada más: **216 failed, 85
errors, 14048 passed** (`-n 4`, 1854.94 s). Por excepción, de las líneas
`E` de los tracebacks:

| Causa | Ocurrencias | Qué es |
|---|---|---|
| API de manager sobre un x2many de `BaseModel` (`.all()`, `.set()`, `.add()`, `.filter()`, `.order_by()`) | ~195 | el campo devuelve un recordset; el consumidor estaba escrito contra el manager de Django. 153 son un solo `.all()` sobre PTAV |
| `PermissionDenied` al leer `product.product` / `product.template` sin usuario | ~44 | la ACL cargada en `5b8f7fea` ya aplica; las pruebas corren sin entorno de superusuario |
| `FieldError: name` en `product.template`, `KeyError` derivados | ~40 | por clasificar; varios son consecuencia de los dos de arriba |

Sitios con API de manager sobre campos del grupo (grep): unos 40 en código
(`stock/models/stock_rule.py` 10, `stock/models/product.py` 10,
`product/services.py` 4, `product/models/product_product.py` 3, …) y unos 45
en pruebas. Decisión: cada sitio pasa a la API de recordset de la fuente
(iterar el recordset, `Command.set`, `filtered`, `sorted`), no a un
adaptador que devuelva un manager; y los directorios de prueba que leen
estos modelos sin usuario ganan el entorno de superusuario de
`TransactionCase` donde la prueba no mide la ACL, como `product` y `fleet`.

## Etapa 1, avance (2026-11-20 16:30Z)

Trabajo en curso, no publicado como código: el parche
`outputs/cluster-wip/stage1-wip-2.patch` (los cuatro cambios de base, los
sitios de `product` y `product_attribute_value.py` vueltos a los cuerpos de
la fuente, y catorce archivos de prueba con `Command.set`/`Command.link`).
Se aplica con `git apply` sobre `7c973a44`.

Re-medido sobre los 16 directorios que fallaban: **143 failed, 20 errors,
6731 passed** (de 216 + 85). Lo que queda:

| Causa | Ocurrencias | Destino |
|---|---|---|
| `PermissionDenied` leyendo `product.template`/`product.product` | ~71 | dos grupos: pruebas sin usuario (≙ `TransactionCase`, entorno de superusuario) y **un camino de producto**: `addons/sale/services.py::confirm_draft_order` lee `lst_price` como el comprador (18). En la fuente el controlador de tienda lee con `sudo()`; hay que portar esa elevación en los flujos de comprador, no sólo en las pruebas |
| `FieldError: name` sobre `product.product` | 14 | un `filter(name=…)` de Django sobre un campo que llega por `_inherits`: pasa a `search([('name', …)])` o al campo del padre |
| API de manager restante (`.all`, `.order_by`, `.count`, `.clear`, `.add` sobre `taxes_id`) | ~25 | igual que el resto: API de recordset |
| `KeyError` / `IndexError` / carrito vacío | ~37 | por clasificar; varios son la respuesta de una vista que falló por los permisos |

## Etapa 1, avance (2026-11-20 17:20Z)

Parche `outputs/cluster-wip/stage1-wip-5.patch` (sobre `4dc72aaa`). Tras
cuatro re-mediciones sobre los archivos que fallaban: 19 fallos en la
cuarta, ya corregidos en el árbol los de API de manager (`taxes`,
`product_variant_ids`, `ptav_product_variant_ids`), la orden por
`_inherits` (`designs/order-by-inherited-field.md`), las pruebas de slug
sobre registros reales y el `sudo()` de registro de
`_add_supplier_to_product` (`odoo19c: purchase_order.py:708`).

Medido además: el entorno de superusuario por directorio **sí** se filtra a
una prueba que mide la ACL con usuarios explícitos
(`test_purchase_security_data.py` daba acceso total); esas pruebas lo
redefinen, como `test_product_security.py`.

Lo que queda y no es de pruebas:

- la API de carrito y lista de deseos responde `403`: el comprador lee
  `product.product` sin fila de ACL. La fuente se la da con la seguridad de
  `website_sale` (público y portal leen el catálogo publicado). Sucesor
  previo a cerrar la etapa: `website-sale-security-data-0397`.
- pruebas cuya premisa era el modelo de Django (`isinstance(..., QuerySet)`,
  `env['product.product'] is ProductProduct`): pasan a la forma de la fuente.
- tres casos por clasificar: el informe (`report_template._render_text`),
  líneas de factura de compra (2 en lugar de 1) y `precision_rounding` 0.

## Etapa 1 — cierre: símbolos que la adopción de `BaseModel` obligó a portar

Medido al cerrar la etapa (suite completa, sin corte por fallo): cada uno
leía un `None` o un gestor de Django donde la fuente lee un recordset.

- `ProductTemplate.product_variant_id` — `odoo19c:
  addons/product/models/product_template.py:247-249`: es
  `product_variant_ids[:1]`, no «la única o `None»`. Quien exige una sola lo
  comprueba con `product_variant_count`. Prueba:
  `tests/unit/stock/test_h_api_680_product_strategy_underscore.py`.
- `ProductTemplate.barcode` — `odoo19c:
  addons/product/models/product_template.py:269-290,341-342`
  (`_compute_template_field_from_variant_field`): el de la variante única, o
  vacío; sin variantes activas reintenta sin `active_test`. Prueba:
  `tests/unit/product/test_product_template_uom_default.py` (vía la
  variante única) y la suite de producto.
- `_get_default_uom_id` y la migración `0045_product_template_uom_default`
  — `odoo19c: addons/product/models/product_template.py:34-36,118-121`:
  `uom_id` toma `uom.product_uom_unit` por defecto y es obligatorio
  (`blank=False`); la columna sigue admitiendo nulo hasta rellenar las filas
  antiguas (`product-uom-uom-extension-0397`). Sin la unidad, el redondeo
  de las órdenes de reabastecimiento leía `0.0`. Prueba:
  `tests/unit/product/test_product_template_uom_default.py`.
- `StockWarehouseOrderpoint._compute_qty_to_order_computed` y
  `StockWarehouseOrderpoint._get_qty_to_order` — `odoo19c:
  addons/stock/models/stock_orderpoint.py:417-419,461-468`: leen
  `product_uom.rounding`; la guarda pasa de `is not None` a la verdad del
  recordset. Prueba: `tests/unit/stock/test_stock_rule_orderpoint_model.py`.
- `_inherits_delegation` (auxiliar de `order_to_django`) — `odoo19c:
  odoo/orm/models.py:5262-5291`, el join del campo heredado de
  `order-by-inherited-field.md`. Prueba:
  `tests/unit/orm/test_order_by_inherited_field.py`.

Sucesor registrado: `environment-companies-from-context-0485` —
`env.companies` lee el ámbito y no `allowed_company_ids` del contexto del
entorno (`odoo19c: odoo/orm/environments.py:255-284`).
