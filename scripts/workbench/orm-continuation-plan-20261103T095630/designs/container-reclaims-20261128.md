# Reclamos del contenedor durante gates F2, 2026-11-28

Evidencia para la hipótesis de H-THYROX-682 («lo que cuenta es el turno; un
`Monitor` que emite por cada paso protege más que uno callado»), registrada
aquí porque esta VM no escribe en el store de Thyrox.

| # | Gate en vuelo | Boot antes → después | Arranque del contenedor | Monitor emitiendo |
|---|---|---|---|---|
| 1 | F2 de `68a38841` | `16588863` | 07:39:18Z | sí, cada 300 s |
| 2 | F2 de `b7e25879` | `16588863` → `65738af1` | 11:51:06Z | sí, cada 240 s; ningún evento antes del reclamo (el primero tocaba a los 4 min) |
| 3 | F2 de `d1d14c71` | `65738af1` → `599aa1e6` | 14:08:56Z | sí: 5 eventos en ~20 min (13:51Z → 14:07Z), el último 2 min antes |

El tercero es el que la regla `local-work-validation.md` nombra como
refutación: un `boot_id` distinto con eventos fluyendo. El log del gate se
escribió por última vez a las 14:08:39Z, 17 s antes del arranque nuevo.

*Métrica:* `boot_id`, `uptime -s` y la marca de tiempo del último evento del
`Monitor` y del log del gate.
*Ciega a:* la regla real de reclamo del anfitrión y cualquier señal que no
sea un evento del `Monitor` (CPU, red, turnos del usuario).

Consecuencia operativa: cada reclamo cuesta el gate en vuelo (≈ 50-58 min) y
el clúster PostgreSQL; el trabajo commiteado sobrevive. Tras cada uno:
`pg_ctlcluster 16 main start` y relanzar el gate desde cero.
