# purchase: cabecera, BaseModel y seguridad

Unidad del plan: `purchase-headers-and-security-0397` (TASK-API-0397).

## El hueco medido (2026-11-14, `odoo-tools@abe4040ec1`)

Métodos de clase por AST, por nombre, en `odoo19c: addons/purchase/models/`
contra `addons/purchase/models/`:

| Archivo | Fuente | Presentes aquí | Ausentes |
|---|---|---|---|
| `purchase_order.py` | 85 | 4 | 81 |
| `purchase_order_line.py` | 47 | 0 | 47 |

En líneas: 1417 + 764 en la fuente contra 470 en los dos archivos de aquí.
La fila del plan describía la unidad como «cabecera y seguridad»; medido,
lo que falta es casi todo el porte de los dos modelos.

Seguridad de la fuente: `security/purchase_security.xml` (14 registros) y
`security/ir.model.access.csv` (36 filas). Aquí no existe `security/`.

*Métrica:* nombres de método definidos en el cuerpo de cada clase.
*Ciega a:* un método presente con el nombre de la fuente que no hace lo que
hace allá (el conteo es generoso), y a los campos, que son otro eje.

## Partición en subunidades, en este orden

1. `purchase-order-header-0397`: `_name`, `_inherit` (los mixins portados),
   `_description`, `_rec_names_search`, `_order` en los dos modelos, y su
   paso a `BaseModel`. Sin métodos nuevos: la adopción y sus consumidores
   (24 archivos nombran el modelo).
2. `purchase-security-0397`: `purchase_security.xml` y el CSV, cargados
   desde el manifiesto, como en `hr` y `hr_homeworking`.
3. `purchase-order-methods-0397`: los 81 métodos de `purchase.order`, por
   familias (estados y acciones, cómputos de montos, facturación, correo y
   portal).
4. `purchase-order-line-methods-0397`: los 47 de `purchase.order.line`.
5. `purchase-requisition-security-0397`: su seguridad, que nombra los
   grupos de (2).

Cada subunidad se diseña, se prueba en rojo y se mide con su anulación
antes de la siguiente. Ninguna se declara cerrada con una divergencia en
lugar del porte.

## Lo que la subunidad 2 necesita antes (medido 2026-11-14)

La seguridad de la fuente no es sólo de `purchase`: de sus 36 filas de
acceso, 21 son sobre modelos de `account`, `product` o `base`, y 6 sobre
cuatro modelos propios de `purchase` que aquí no existen
(`purchase.bill.union`, `purchase.report`, `purchase.bill.line.match`,
`bill.to.po.wizard`; `grep -rln "_name = '<modelo>'"` da 0 en los cuatro).
Nombra los grupos `account.group_account_readonly` y
`account.group_account_invoice`, que tampoco existen aquí, y la categoría
`base.module_category_supply_chain`.

Orden que se sigue de esto:

1. dependencias del manifiesto (`account`, `analytic`) y hogar de
   `product.catalog.mixin`: subunidad `purchase-order-mixins-0397`;
2. la seguridad de `account` con sus grupos, si no está ya portada en otra
   unidad;
3. los cuatro modelos propios que la seguridad nombra;
4. entonces la seguridad de `purchase`, entera.

Portar ahora sólo las filas cuyos modelos existen dejaría un CSV parcial
presentado como la seguridad de `purchase`; no se hace.
