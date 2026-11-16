# Seguridad de `purchase` — diseño

Unidad: `purchase-headers-and-security-0397` (citada a `TASK-API-0122`).
Fuente: `odoo19c: purchase/security/purchase_security.xml` (13 registros) e
`ir.model.access.csv` (35 filas), LGPL-3, `odoo-tools@abe4040ec1`.

## Precondiciones (medidas 2026-11-16)

| Pieza | Estado |
|---|---|
| seguridad de `account` (grupos y modelos citados) | cargada, `account-security-0121` |
| `base.module_category_supply_chain` | en la base (migración 0090) |
| `purchase.model_purchase_order[_line]` | en la base (cabecera `purchase-order-header-0397`) |

## Forma

La de `account` y `hr`: copia fiel del XML con sus omisiones declaradas en la
cabecera, CSV sin las filas cuyo modelo no tiene fila en `ir.model`, y la
clave `data` del manifest en el orden de la fuente.

## Omisiones esperadas y su causa

| Omisión | Causa | Sucesor |
|---|---|---|
| `group_purchase_manager.user_ids` | `base.user_root`/`base.user_admin` no existen aquí | — (la configuración crea usuarios) |
| `purchase_bill_union_comp_rule`, `purchase_order_report_comp_rule` | `purchase.bill.union` y `purchase.report` no tienen puerto | `purchase-report-models-0122` |
| 3 filas de `purchase.bill.line.match`, 1 de `bill.to.po.wizard`, 1 de `purchase.bill.union`, 2 de `purchase.report` | sin puerto | `purchase-report-models-0122` |
| `product.supplierinfo`, `product.pricelist.item` (1 fila cada uno) | portados sin `_name` | `product-model-headers-0122` |
| `account.analytic.line` (1 fila) | portado sin `_name` | `analytic-model-headers-0121` |

## Pruebas

1. Datos: grupos, privilegio, implicaciones, reglas y filas de acceso, con las
   expectativas leídas de la fuente; la fixture retira lo que `purchase` cargó
   al crear la base antes de medir (la lección de `account-security`).
2. Aprobación en dos niveles, con usuarios reales de los grupos cargados:
   - `group_purchase_user` confirma por debajo del umbral; por encima la orden
     queda en `to approve`;
   - el usuario sin `group_purchase_manager` no aprueba (`button_approve`);
   - `group_purchase_manager` aprueba;
   - sin grupo de compras no hay acceso a `purchase.order`.

Anulación: retirar el CSV del manifest hace caer las pruebas de acceso; retirar
el chequeo de grupo de `_approval_allowed` hace caer la del usuario que no
aprueba.

## Resultado (2026-11-16)

12 de 14 registros del XML y 25 de 35 filas del CSV, con las omisiones de la
tabla de arriba declaradas en la cabecera y en el manifest. La carga no
destapó huecos nuevos del ORM: los de `account-security-0121` ya estaban
cerrados.

Tres correcciones de la propia prueba, medidas:

- el usuario de compras tiene borrado sobre `purchase.order` (la fila
  `access_purchase_order` es `1,1,1,1`); la primera expectativa decía lo
  contrario sin haber leído la fuente;
- el enlace de `base.group_user` a `group_send_reminder` está en un bloque
  `noupdate="1"`: la fuente lo escribe al instalar y lo salta al actualizar
  (`if self.noupdate and self.mode != 'init'`). Se prueba cargando el archivo
  en modo `init`, con el entorno del superusuario como el ciclo real;
- las reglas `purchase_order_comp_rule` filtran por `company_ids`: el usuario
  actúa como miembro de la empresa de la orden y con ella activada
  (`company_scope`).

Controles de anulación:

| Anulación | Caen | Sobreviven |
|---|---|---|
| `_approval_allowed` devuelve `True` sin mirar el grupo | 2 (el usuario deja la orden en `to approve`; no la aprueba) | las otras 3 de aprobación |
| sin `security/ir.model.access.csv` en el manifest | 7 (acceso y las 5 de aprobación) | 5 (grupos, privilegio, reglas, modo `init`, usuario interno) |

La del usuario interno sin acceso es un control negativo y no discrimina el
CSV: pasa con él y sin él.

*Ciega a:* el flujo de aprobación de una orden de otra empresa que el usuario
no tiene activada (lo cubren las reglas, no esta prueba) y a las vistas y
menús, que el puerto no tiene.
