---
name: kanban-wip-limits
description: "Use when calculating and applying Work In Progress limits per column or person to maximize flow and expose bottlenecks. kanban:wip-limits — set WIP limits with Little's Law, turn the board into a pull system, and make the team swarm to unblock instead of starting new work when a limit is reached."
allowed-tools: Read Glob Grep Bash Write Edit
effort: medium
disable-model-invocation: true
metadata:
  triggers: ["WIP limits", "work in progress", "pull system", "Little's Law", "bottleneck", "stop starting start finishing"]
updated_at: 2026-06-02
---

# /kanban-wip-limits — Kanban: WIP Limits

> *"Stop starting, start finishing. Work in progress is not productivity — it is inventory that ages, hides defects and inflates lead time. A WIP limit is the discipline that converts a board of busy people into a system that actually delivers. The limit hurts on purpose: the pain is the bottleneck becoming visible."*

Calcula y aplica los **límites WIP (Work In Progress)** por columna y por persona para maximizar el flujo y exponer los cuellos de botella. El límite WIP convierte el tablero en un **pull system**: el trabajo no se empuja hacia adelante, se *jala* cuando hay capacidad libre. La relación cuantitativa la da la **Little's Law**: `WIP = throughput × lead time` — reducir WIP a throughput constante reduce lead time de forma directamente proporcional.

**THYROX Stage:** Stage 8 PLAN EXECUTION / Stage 11 TRACK-EVALUATE.

**Outputs clave:** límites WIP por columna · señales de pull · cuellos identificados.

---

## Pre-condición

Requiere:
- Un tablero Kanban con columnas que reflejan el flujo real y políticas explícitas (`kanban-board-setup`)
- Tamaño del equipo y cuántas personas trabajan en paralelo por columna activa
- Idealmente, datos de flujo iniciales (throughput y lead time) para calibrar con Little's Law; si no existen, se arranca con un límite empírico y se ajusta con métricas

---

## Cuándo usar este paso

- Cuando el tablero ya visualiza el flujo pero el equipo trabaja en demasiadas tarjetas a la vez y nada termina
- Cuando el lead time crece sin que el throughput mejore — señal de exceso de WIP
- Cuando hay columnas `done` llenas de tarjetas terminadas que la siguiente columna no jala (cuello de botella visible)
- Al instrumentar un pull system por primera vez sobre un tablero existente

## Cuándo NO usar este paso

- Sobre un tablero cuyas columnas no reflejan el flujo real — primero arreglar el tablero (`kanban-board-setup`), un límite sobre un modelo falso gestiona una ficción
- Para fijar límites por decreto sin observar el flujo ni revisarlos con datos — un límite arbitrario que nunca se ajusta es tan dañino como no tener límite

---

## Cálculo del límite WIP

### Little's Law como base cuantitativa

La relación fundamental del flujo es:

```
WIP = throughput × lead time
```

Despejando, el lead time es proporcional al WIP a throughput constante: `lead time = WIP / throughput`. Por eso bajar el WIP es la palanca más directa para acortar el lead time sin contratar más gente. Si el equipo entrega `throughput = 5 tarjetas/semana` y quiere un `lead time` objetivo de `1 semana`, el WIP del sistema debe rondar `5` tarjetas.

### Heurística de arranque por columna

Cuando aún no hay datos de flujo, se arranca con una heurística y se calibra después:

| Columna | Heurística inicial | Razón |
|---------|--------------------|-------|
| En desarrollo | nº de personas que codean, o `personas + 1` | Una tarjeta activa por persona; el `+1` permite un bloqueo sin parar a todos |
| Review | `≈ mitad del WIP de desarrollo` | Review es rápido; un límite bajo fuerza a revisar antes de seguir codeando |
| QA / E2E | calibrar con el throughput real | Suele ser el cuello; el límite lo hace visible |
| Buffers `done` | límite compartido con la columna activa vecina | Evita acumular inventario terminado sin jalar |

El límite se escribe **visible en la cabecera de la columna** (`En desarrollo (3)`). Un límite que no está escrito en el tablero no existe.

### Señal de pull

El pull system funciona así: una persona **solo** toma trabajo nuevo cuando la columna destino tiene un hueco bajo su límite. Si la columna está en su límite, la señal es clara — **no se empieza nada nuevo**.

```
Stop starting, start finishing.
```

Al alcanzar el límite, la respuesta correcta no es esperar pasivamente ni saltarse el límite: es **swarming** — el equipo converge a desbloquear o terminar la tarjeta que retiene el cuello, aguas abajo, en lugar de abrir frente nuevo aguas arriba.

---

## Actividades

| Actividad | Output | Técnica clave |
|-----------|--------|---------------|
| **1. Medir flujo inicial** | throughput + lead time actuales | Little's Law para dimensionar el WIP del sistema |
| **2. Fijar límites por columna** | Límite visible en cada cabecera | Heurística de arranque + nº de personas |
| **3. Instrumentar el pull** | Regla de "no jalar si la columna está llena" | Política explícita de pull en el tablero |
| **4. Definir la respuesta al límite** | Protocolo de swarming | Ayudar a desbloquear, no empezar trabajo nuevo |
| **5. Ajustar con métricas** | Límites revisados | CFD / cycle time exponen si el límite está mal calibrado |

---

## Criterio de completitud — ¿Pull system operativo?

**Pull system operativo (todos los siguientes):**
1. Cada columna activa tiene un límite WIP escrito y visible en su cabecera
2. La señal de pull es explícita: nadie jala trabajo nuevo si la columna destino está en su límite
3. Existe un protocolo acordado de swarming cuando se alcanza el límite
4. El cuello de botella es observable en el tablero (columna que satura su límite o `done` que no se jala)
5. Los límites se revisan con métricas de flujo (throughput, lead time, CFD) y se ajustan

**Requiere más iteración:**
- Columnas activas sin límite — el WIP es ilimitado y el cuello queda oculto
- Límite presente pero ignorado ("solo esta vez empiezo otra") — el límite que se rompe sin disciplina no es un límite
- Límites fijados una vez y nunca revisados con datos reales

---

## Artefacto esperado

`{wp}/plan-execution/wip-limits.md` (límites por columna, cálculo con Little's Law, protocolo de pull y swarming, bitácora de ajustes con su evidencia de flujo).

---

## Red Flags — señales de WIP mal gestionado

- **Columna activa sin límite** — WIP ilimitado; el equipo arranca todo y termina poco, y el cuello de botella nunca se hace visible
- **Límite que se rompe "por excepción"** — cada excepción aceptada erosiona la disciplina hasta que el límite es decorativo
- **Empezar trabajo nuevo al alcanzar el límite** — el anti-patrón central; el reflejo correcto es ayudar a desbloquear aguas abajo, no abrir un frente nuevo aguas arriba
- **Límites idénticos durante meses** — si el throughput cambió y los límites no, dejaron de estar calibrados; la retrospective y el CFD deben moverlos
- **WIP alto con throughput plano** — síntoma de Little's Law en contra: el lead time se infla sin que se entregue más; el inventario solo envejece
- **Límite por persona inexistente** — una persona con 4 tarjetas "en progreso" a la vez no tiene WIP real de 1; el multitasking esconde el cuello

---

## Integración con otros namespaces

- **`lean:` (flujo, eliminar desperdicio):** el límite WIP es la implementación directa del principio Lean de pull y de la reducción de inventario en proceso. El exceso de WIP es uno de los desperdicios Lean (inventario / sobreproducción); el límite lo ataca en su raíz y fuerza el flujo de una pieza (one-piece flow) hacia el que tiende Lean.
- **`bpa:` (mapeo de proceso):** el mapa de proceso As-Is de `bpa-map` revela dónde se acumula trabajo entre actividades; esas acumulaciones son los puntos donde el límite WIP debe morder primero para exponer el cuello. El análisis de cuellos de `bpa-analyze` y los límites WIP se retroalimentan.
- **`kanban-board-setup`:** los límites WIP se aplican sobre las columnas que ese skill definió; sin un tablero con columnas reales y políticas explícitas, el límite gestiona un modelo falso. Es su paso siguiente natural.
- **`kanban-flow-metrics`:** la calibración de los límites depende de las métricas de flujo (throughput, lead time, Cumulative Flow Diagram). El CFD muestra las bandas que se ensanchan donde el WIP se acumula; esa evidencia es la que justifica subir o bajar un límite, cerrando el ciclo con Little's Law.
- **Ciclo THYROX:** los límites WIP se fijan en Stage 8 PLAN EXECUTION (instrumentar el pull system al planear la ejecución) y se ajustan en Stage 11 TRACK-EVALUATE (con throughput y lead time reales se recalibra el límite y se evalúa si el flujo mejoró).

---

## Limitaciones

- El límite WIP expone el cuello de botella pero no lo resuelve — hacerlo visible es el primer paso; eliminarlo requiere acción del equipo (swarming, automatizar el gate, redistribuir capacidad)
- Un límite demasiado bajo deja a personas ociosas con capacidad sin usar; uno demasiado alto no fuerza el flujo — el valor está en calibrarlo con datos, no en el número en sí
- Little's Law asume un sistema estable (entradas ≈ salidas en el periodo); en un sistema muy variable o con tarjetas de tamaño muy dispar, el WIP calculado es una guía, no una garantía — la distribución del cycle time (ver `kanban-flow-metrics`) complementa la media

---

## Siguiente paso

- Pull system operativo con límites calibrados → `kanban-flow-metrics` (medir cycle time, lead time, throughput y construir el CFD para evaluar y reajustar)
- Cuello de botella expuesto pero persistente → swarming del equipo + análisis de causa raíz (`lean:` / `bpa-analyze`) antes de subir el límite para "tapar" el síntoma
