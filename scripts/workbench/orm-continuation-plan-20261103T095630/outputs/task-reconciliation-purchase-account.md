# Reconciliación de TASK de las unidades purchase y account

Medido el 2026-11-15 sobre el store del proveedor, en sólo lectura
(`sqlite3 file:agent-results/agent_store.sqlite3?mode=ro`):

| Cita | Sujeto | Estado |
|---|---|---|
| `TASK-API-0397` | Construir BaseModel propio desde el contrato medido de la referencia | in_progress |
| `TASK-API-0121` | Capa 0 · account, mail, stock, web, sale_project, payment_stripe (4084 def) | in_progress |
| `TASK-API-0122` | Capa 1 · mrp, website, project, hr, purchase y cinco más (2652 def) | pending |

El ordinal `#397` de board («Familia web») es otro sujeto: es la colisión de
ordinales entre sesiones que `task_ids.py` mide. La cita durable es la que
vale.

## Lo que la medición corrigió

Las unidades purchase llevaban `TASK-API-0397` por asignación del plan, no por
el inventario: `inventory_by_kind.tsv` (2513 filas) cubre `src/orm`, y ninguna
fila nombra `addons/purchase` ni `addons/account`.

- **Se queda en 0397** lo que es adopción del contrato de BaseModel: la
  cabecera de `purchase.order` (`purchase-order-header-0397`) y sus mixins.
- **Es porte de negocio de purchase (`TASK-API-0122`)**: máquina de estados,
  proveedor en producto, secuencia, enlace con facturas, seguridad, producto,
  validación analítica, órdenes desde factura.
- **Es porte de account (`TASK-API-0121`)**: cabeceras de modelos de account,
  `_check_company_auto`, `_inherits` de la línea de extracto, atributos de
  `sequence.mixin` y `_copy_data_extend_business_fields`.

## Lo que se hizo

- Las cinco unidades **pendientes** de negocio se volvieron a citar en
  `plan.jsonl` (4 a `TASK-API-0122`, 1 a `TASK-API-0121`).
- Las unidades **ya aceptadas** con sufijo `-0397`
  (`purchase-order-state-machine-0397`, `purchase-order-sequence-0397`,
  `purchase-invoice-link-0397`, `purchase-add-supplier-to-product-0397`,
  `purchase-res-company-0397`, `purchase-order-partner-0397`) **no se
  reescriben**: `outputs/continuation.jsonl` es un registro de lo ocurrido. Su
  TASK de alcance es `TASK-API-0122`. Este archivo es la corrección.
- Ninguna TASK nueva: las tres citas existen en el store.

*Métrica:* filas de `tasks` por `citation_id`; filas del inventario por módulo.
*Ciega a:* el alcance que el ejecutor quiera dar a 0397; la asignación de
arriba sigue al sujeto de cada TASK, no a una decisión suya.
