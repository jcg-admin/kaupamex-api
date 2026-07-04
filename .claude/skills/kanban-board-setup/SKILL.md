---
name: kanban-board-setup
description: "Use when designing the Kanban board — defining columns (workflow states), explicit entry/exit policies per column, classes of service, and the value-stream mapping. kanban:board-setup — make the work visible so the team manages flow on a board that reflects how work actually moves."
allowed-tools: Read Glob Grep Bash Write Edit
effort: medium
disable-model-invocation: true
metadata:
  triggers: ["Kanban board", "workflow columns", "explicit policies", "classes of service", "visualize work"]
updated_at: 2026-06-02
---

# /kanban-board-setup — Kanban: Board Setup

> *"You cannot manage what you cannot see. The board is not decoration — it is the model of your workflow. If the board shows an idealized process while work actually flows differently, the board lies, and every decision made from it is wrong. Map the real flow first."*

Diseña el **tablero Kanban**: las columnas que representan los estados reales del flujo de trabajo, las **políticas explícitas** de entrada/salida por columna, las **clases de servicio** que distinguen tipos de trabajo, y el mapeo del flujo de valor. El primer principio de Kanban es *visualizar el trabajo*: el tablero hace observable lo que de otro modo vive en la cabeza de cada persona.

**THYROX Stage:** Stage 6 SCOPE / Stage 8 PLAN EXECUTION.

**Outputs clave:** tablero Kanban · políticas explícitas · clases de servicio.

---

## Pre-condición

Requiere:
- Comprensión del flujo de valor real (cómo se mueve una tarjeta de "idea" a "entregado")
- Tipos de trabajo identificados (feature, bug, deuda técnica, hotfix)
- La Definition of Done del equipo (alimenta la política de salida de la última columna activa)

---

## Cuándo usar este paso

- Al arrancar el trabajo de un equipo que aún no visualiza su flujo
- Cuando el tablero actual no refleja cómo el trabajo se mueve de verdad (columnas idealizadas)
- Cuando aparecen estados "ocultos" donde las tarjetas se estancan sin que el tablero lo muestre (p. ej. "esperando review", "esperando deploy")

## Cuándo NO usar este paso

- Para imponer un proceso ideal que el equipo no sigue — el tablero modela el flujo real, no el deseado
- Para añadir columnas decorativas sin política de entrada/salida — una columna sin política es solo un cubo donde el trabajo desaparece

---

## Anatomía del tablero

### Columnas — estados del flujo real

Cada columna es un estado por el que pasa el trabajo. Las columnas activas (donde se trabaja) suelen partirse en **doing / done** para hacer visible el handoff:

```
Backlog │ Análisis │ En desarrollo │ Review │ QA / E2E │ Listo deploy │ Hecho
        │ doing|done│ doing|done    │        │ doing|done│              │
```

El split `doing|done` expone el trabajo terminado en una columna pero aún no jalado por la siguiente — el síntoma visible de un cuello de botella aguas abajo.

### Políticas explícitas — el segundo principio de Kanban

Cada columna tiene una **política de entrada** (qué condiciones cumple una tarjeta para entrar) y una **política de salida / "Done" de columna** (qué condiciones cumple para pasar a la siguiente). Sin políticas explícitas, el avance de tarjetas es subjetivo y arbitrario.

| Columna | Política de entrada | Política de salida ("Done" de columna) |
|---------|---------------------|----------------------------------------|
| Análisis | Tarjeta priorizada, con acceptance criteria | Criterios claros, sin bloqueos de info |
| En desarrollo | Diseño/decisión técnica resuelta | Código + tests unitarios; lazy imports = 0 |
| Review | PR abierto contra la rama padre | Code review aprobado (Tim Pope commits) |
| QA / E2E | Rama desplegable | api `uv run pytest --create-db` + ui jest + Playwright verdes |
| Listo deploy | DoD completa | Mergeado y gitlink bumpeado si toca submódulo |

La política de salida de la última columna activa **es la Definition of Done** — el tablero la materializa.

### Clases de servicio — distinguir tipos de trabajo

No todo el trabajo fluye igual. Las clases de servicio definen políticas de prioridad y SLA distintos:

| Clase | Ejemplo | Política de flujo |
|-------|---------|-------------------|
| **Expedite** | Hotfix de producción (pago caído) | Jalado de inmediato; rompe WIP si hace falta; carril propio |
| **Fixed date** | Cumplimiento legal con fecha | Se planifica hacia atrás desde la fecha comprometida |
| **Standard** | Feature normal del backlog | FIFO dentro de su prioridad |
| **Intangible** | Deuda técnica, refactor | Se reserva capacidad fija para que no sea desplazada siempre |

---

## Actividades

| Actividad | Output | Técnica clave |
|-----------|--------|---------------|
| **1. Mapear el flujo de valor real** | Value-stream map | Observar cómo fluye una tarjeta de verdad, no el ideal |
| **2. Derivar columnas del flujo** | Columnas con split doing/done | Una columna por estado real, incluidos los "ocultos" |
| **3. Escribir políticas explícitas** | Política entrada/salida por columna | "Done" de columna verificable |
| **4. Definir clases de servicio** | Clases con su política de flujo | Expedite / fixed-date / standard / intangible |
| **5. Asignar dueño visible** | 1 dueño por tarjeta | Avatar/asignado en cada tarjeta activa |

---

## Criterio de completitud — ¿Tablero operativo?

**Tablero operativo (todos los siguientes):**
1. Las columnas reflejan el flujo **real**, no el idealizado (incluidos los estados de espera ocultos)
2. Cada columna tiene política de entrada y política de salida ("Done" de columna) explícitas
3. Las clases de servicio están definidas con su política de flujo
4. Cada tarjeta tiene un único dueño visible
5. El flujo de valor está mapeado de extremo a extremo

**Requiere más iteración:**
- Columnas sin política de salida — el avance es subjetivo
- Tarjetas sin dueño o con varios dueños — nadie es responsable del avance
- El tablero contradice cómo el equipo trabaja de verdad — el modelo es falso

---

## Artefacto esperado

`{wp}/plan-execution/kanban-board.md` (diseño del tablero: columnas, políticas, clases de servicio, value-stream map).

---

## Red Flags — señales de tablero mal diseñado

- **Columnas idealizadas** — el tablero muestra un proceso limpio que nadie sigue; las tarjetas saltan estados o retroceden sin que el tablero lo refleje
- **Estados de espera ocultos** — el trabajo se estanca en "esperando review" o "esperando deploy" pero no hay columna que lo muestre; el lead time se infla sin causa visible
- **Columnas sin política** — un cubo sin "Done" de columna; cada quien decide cuándo una tarjeta avanza
- **Tarjeta sin dueño o con varios** — la accountability se diluye igual que un RACI con múltiples A
- **Sin clases de servicio** — un hotfix de producción espera en la misma cola FIFO que un refactor de baja prioridad
- **Tablero que no se mira** — si el equipo coordina por chat y el tablero está desactualizado, dejó de ser el modelo del flujo

---

## Integración con otros namespaces

- **`lean:` (flujo, eliminar desperdicio):** el tablero Kanban es la herramienta de visualización que hace observable el desperdicio Lean — esperas (tarjetas en `done` sin jalar), sobreproducción (demasiado WIP), retrabajo (tarjetas que retroceden). El value-stream map de `lean` alimenta directamente las columnas del tablero.
- **`bpa:` (mapeo de proceso):** el As-Is que `bpa-map` documenta con BPMN/swimlanes es la fuente del flujo real. Las columnas del tablero son la proyección operativa de ese mapa de proceso: cada actividad/estado del proceso mapeado se vuelve una columna con su política.
- **`scrum-definition-of-done`:** la política de salida de la última columna activa **es** la Definition of Done. El tablero materializa la DoD como gate visible; sin DoD, esa columna no tiene "Done" verificable.
- **Ciclo THYROX:** el tablero se diseña en Stage 6 SCOPE (qué flujo de valor se va a gestionar) y se instrumenta en Stage 8 PLAN EXECUTION (el tablero operativo con políticas y clases de servicio listo para ejecutar).

---

## Limitaciones

- El tablero modela el flujo, no lo mejora por sí solo — visualizar un cuello de botella no lo resuelve; eso requiere límites WIP (`kanban-wip-limits`) y acción del equipo
- Un tablero con demasiadas columnas y clases de servicio se vuelve ruido — empezar con el flujo mínimo real y refinar; la granularidad excesiva esconde la señal
- El tablero refleja el estado en un momento; sin disciplina de actualización en tiempo real, diverge de la realidad y vuelve a mentir

---

## Siguiente paso

- Tablero operativo con políticas y clases de servicio → `kanban-wip-limits` (aplicar límites WIP por columna para gestionar el flujo)
- Flujo real aún no claro → volver al value-stream map (`lean:` / `bpa:map`) antes de fijar columnas
