# Cualificación de continuidad autónoma (instrucción 4.3.0 §7.6)

Fecha: 2026-11-17. Controlador usado: el existente del Consumer
(`plan.jsonl`, `outputs/continuation.jsonl`, `probes/settle_item.py`,
`probes/persist_gate_evidence.py`). No se creó un coordinador paralelo.

| # | Caso | Estado | Evidencia |
|---|---|---|---|
| 1 | Dos unidades admitidas consecutivas sin nueva selección del usuario | **demostrado** | `continuation.jsonl`: `accepted` de `mail-source-resolution-0121` (`a29e8bc3`, 08:31:37Z) y de `purchase-line-track-qty-received-0122` (`42e34c95`, 08:33:03Z), seleccionadas de la frontera calculada desde el plan |
| 2 | Reanudación de una ejecución interrumpida desde su estado persistido | **demostrado en esta sesión** | tras la compactación del contexto, F2 de Mail se recuperó por su log y su proceso (`fullgate-mail.log`, 93 % → resultado), sin relanzarla |
| 3 | Claims y prevención de ejecutores duplicados | **no cualificado** | ningún segundo ejecutor compitió por una unidad en esta sesión; el mecanismo de claims no se ejercitó |
| 4 | Recuperación de un gate terminado cuyo resultado no estaba asentado | **demostrado** | F2 de la corrección de caché terminó con un fallo; se leyó, se corrigió (`44ce4bcf`) y se registró (`99b66cf7`, corrección `92d153e4`) |
| 5 | Continuidad tras terminar el proceso conversacional | **no demostrado** | no existe supervisor persistente: un reclamo del contenedor mata los procesos de segundo plano (H-THYROX-606, H-THYROX-633). Capacidad faltante: un supervisor que, al arrancar el contenedor, lea `continuation.jsonl` y relance o asiente el último gate. Interfaz compatible: el ledger `wait-jobs` del proveedor, que este Consumer no modifica |

## Frontera tras los asentamientos

Calculada desde `plan.jsonl` y los `accepted` de `continuation.jsonl`: 234
aceptadas, 45 pendientes, 35 listas. Siguiente unidad seleccionada:
`purchase-line-price-and-dates-0122`, que dependía de piezas sin unidad:
registradas `account-tax-included-price-0121`,
`account-fiscal-position-resolution-0121` (TASK-API-0121) y
`purchase-order-fiscal-header-0535` (TASK-GEN-0535) en `aba21557`.

## Lo que no está demostrado

El caso 5. Ninguna afirmación de este registro dice que el trabajo continúe
sin una sesión activa.
