# Investigación: filas `xfail` restantes del contrato de política de borrado

Fecha: 2026-11-17. Revisión base: `d904519e`. Investigador de sólo lectura
(no ejecutó pytest ni tocó el repositorio).

| Lote | Propuesta | Nivel |
|---|---|---|
| 0 | `proposals/lot-0-remaining-xfail-rows.md` | 3 — declarada; el conteo (71 = 46 + 25, todas las `set null` con `null=True`) lo reprodujo el coordinador: nivel 2 sólo para ese conteo |
| 1 | `proposals/lot-1-block-e-and-restrict-rows.md` (base `286faed0`, escrito por el investigador directamente aquí) | 3 — declarada, sin verificar |

## Lo que la propuesta afirma (sin promover)

- 71 filas paramétricas `xfail` y 2 `xfail` de ORM; no 73 paramétricas.
- 25 `restrict` (22 hacia `res.company`, 2 de `account.partial.reconcile`,
  1 `stock.StockRule.picking_type`) y 46 `set null`. El diseño
  `restrict-ondelete-non-company.md` dice 20 y 47.
- Clases: 66 SOLO_ON_DELETE, 3 REQUIERE_UNLINK_OVERRIDE, 0 REQUIERE_NULL,
  2 DESCONOCIDO.

## Filas abiertas (se conservan)

| Fila | Estado |
|---|---|
| las 2 de `CORRECTED` fuera de la población destructiva | UNVERIFIED — el investigador no las identificó |
| `account.AccountBankStatementLine.company` | DESCONOCIDO — `related` y `required`; falta el SQL que genera la fuente |
| `hr.HrVersion.employee` | DESCONOCIDO — falta medir el borrado bajo `_inherits` |
| consumidores que borran una empresa en cascada | MISSING — sin medir |
| `IrModel.delete` frente a `ir_model.py:354-380`, `:980-1010` | UNVERIFIED |

El coordinador reproduce cada comprobación decisiva antes de implementar
un bloque; nada de esto es nivel 2 todavía.

## Lote 1 (2026-11-17): lo que afirma, sin promover

- `hr.HrVersion.employee`: basta `SET_NULL`; la fuente no recorre
  `_inherits` al borrar.
- `project.ProjectTask.project`: `Project` necesita `BaseModel` y un
  `unlink` que borre sus tareas antes de `super()`.
- Parciales de conciliación: `remove_move_reconcile` se llama desde
  `AccountMoveLine.unlink` **y** desde `AccountMove.unlink`.
- `stock.StockRule.picking_type`: sólo la política.
- 22 filas hacia `res.company`: `PROTECT`; 7 archivos de prueba borran una
  empresa y ninguno crea hijos de esas filas.

| Fila abierta | Estado |
|---|---|
| DDL real de la fuente para `AccountBankStatementLine.company` | UNVERIFIED |
| tamaño de adoptar `BaseModel` en `AccountMove`, `AccountMoveLine`, `AccountPartialReconcile` | MISSING — el mayor riesgo del bloque C |
| `_unlink_except_last_version` de HR y versiones huérfanas | UNVERIFIED |
| borrados de empresa fuera de la heurística estática | UNVERIFIED |
| `StockRule.picking_type` es `null=True` aquí y `required` en la fuente | divergencia previa, sin tratar |
