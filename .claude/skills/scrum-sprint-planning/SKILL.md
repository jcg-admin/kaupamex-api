---
name: scrum-sprint-planning
description: "Use when planning a Scrum Sprint — selecting backlog items, defining the Sprint Goal and building the Sprint Backlog. scrum:sprint-planning — seleccionar items del Product Backlog priorizado, fijar un Sprint Goal único y medible, descomponer en tareas, estimar en story points (Fibonacci) y confirmar capacidad del equipo."
allowed-tools: Read Glob Grep Bash Write Edit
effort: medium
disable-model-invocation: true
metadata:
  triggers: ["sprint planning", "sprint goal", "sprint backlog", "story points", "team capacity", "iteration planning"]
updated_at: 2026-06-02
---

# /scrum-sprint-planning — Scrum: Sprint Planning

> *"El Sprint Planning responde a tres preguntas: ¿por qué este Sprint es valioso? (Sprint Goal), ¿qué se puede entregar? (selección del backlog), y ¿cómo se hará el trabajo? (Sprint Backlog). Un Sprint sin Goal claro es solo una lista de tareas con fecha límite — el Goal es lo que convierte un conjunto de items en un compromiso coherente."*

Ejecuta el evento **Sprint Planning** de Scrum. Selecciona items del **Product Backlog** priorizado por valor, define un **Sprint Goal** único y medible, construye el **Sprint Backlog** descomponiendo cada item en tareas técnicas, estima en **story points** (Fibonacci) y confirma que el compromiso cabe en la capacidad del equipo. El output es un Sprint arrancable con un objetivo que el equipo entiende y puede comprometer.

**THYROX Stage:** Stage 6 SCOPE / Stage 8 PLAN EXECUTION.

**Outputs clave:** Sprint Goal · Sprint Backlog · capacity plan.

---

## Pre-condición

Requiere, antes de iniciar la sesión de planning:
- **Product Backlog priorizado** — historias de usuario ordenadas por valor en `docs/source/requisitos/historias-usuario/`, cada una derivada de un `UC-XXX` (ver `scrum-backlog-refinement`).
- **Velocity histórica** — story points completados en los últimos 3 Sprints (promedio o rango), o un capacity inicial estimado si es el Sprint 1.
- **Definition of Ready (DoR)** — los items candidatos al tope del backlog ya pasaron refinamiento y cumplen DoR.

Sin backlog priorizado y refinado, no hay Sprint Planning: regresar a `scrum-backlog-refinement`.

---

## Cuándo usar este paso

- Al inicio de cada Sprint, una vez que el Sprint anterior cerró (Sprint Review + Retrospective).
- Cuando el equipo necesita convertir el tope del Product Backlog en un compromiso concreto con objetivo.
- En el e-commerce Kaupamex: al planificar un Sprint que entregará un incremento del checkout, catálogo o panel de administración basado en historias de `historias-usuario/`.

## Cuándo NO usar este paso

- Sin backlog priorizado ni DoR cumplida — planificar sobre items ambiguos produce compromisos que no se cumplen; refinar primero.
- Para mantener la salud general del backlog o desglosar épicas — eso es `scrum-backlog-refinement`, no Sprint Planning.
- Cuando no hay velocity ni baseline de capacidad y el equipo es nuevo — usar un Sprint 0 conservador en lugar de sobrecomprometer.

---

## Actividades

| Actividad | Output | Técnicas clave |
|-----------|--------|----------------|
| **1. Revisar backlog priorizado** | Lista de candidatos por valor | Ordenamiento por valor de negocio, lectura de historias en `historias-usuario/` |
| **2. Definir Sprint Goal** | Sprint Goal único y medible | Objetivo de negocio coherente que une los items seleccionados |
| **3. Seleccionar hasta capacity** | Subconjunto comprometido | Suma de puntos ≤ velocity; pull, no push |
| **4. Descomponer en tareas** | Sprint Backlog (tareas técnicas) | Task breakdown ≤ 1 día por tarea |
| **5. Estimar** | Story points por item | Planning poker, Fibonacci 1·2·3·5·8·13 |
| **6. Confirmar capacidad** | Capacity plan | Días disponibles − ausencias − overhead; comprometer Goal |

---

## Escala de estimación — story points (Fibonacci)

Estimación **relativa**, no en horas. La serie 1·2·3·5·8·13 separa magnitudes:

| Puntos | Significado | Acción |
|--------|-------------|--------|
| 1, 2 | Trivial / pequeña — entendida por completo | Lista para el Sprint |
| 3, 5 | Mediana — esfuerzo claro, riesgo acotado | Lista para el Sprint |
| 8 | Grande — al límite de un Sprint | Considerar descomponer |
| 13 | Demasiado grande / incierta | **Desglosar** antes de comprometer — no entra como un solo item |

Un item de 13 que llega a planning es señal de refinamiento incompleto: devolver al backlog para descomponer en historias menores.

---

## Sprint Goal — criterios

El Sprint Goal NO es la lista de items; es el **por qué** que los une. Debe ser:

- **Único** — un solo objetivo por Sprint, no tres objetivos disjuntos.
- **Medible** — se puede verificar si se cumplió o no al final del Sprint.
- **De negocio** — expresado en valor para el usuario/producto, no en tareas técnicas.

Ejemplo (Kaupamex): *"El comprador puede completar una compra de extremo a extremo pagando con Mercado Pago"* — medible (la compra se completa o no), de negocio (valor para el comprador), y une las historias de carrito, checkout y pago bajo un solo objetivo.

---

## Quality gates — ¿Sprint Planning completo?

**Planning aprobado (todos los siguientes):**
1. **Sprint Goal único y medible** — un solo objetivo, verificable al cierre del Sprint.
2. **Cada item cumple Definition of Ready** — sin DoR, el item no entra al Sprint Backlog.
3. **Suma de story points ≤ velocity** — el compromiso cabe en la capacidad histórica del equipo, no la excede.
4. Cada item del Sprint Backlog está descompuesto en tareas técnicas estimables (≤ 1 día).
5. El equipo confirma el compromiso por pull (lo toma), no por push (no se le impone).

**Requiere más trabajo antes de arrancar el Sprint:**
- Hay items sin DoR en la selección → devolver a `scrum-backlog-refinement`.
- La suma de puntos excede la velocity → recortar alcance hasta que quepa.
- Aparece un item de 13 puntos sin descomponer → desglosar antes de comprometer.
- El Sprint Goal abarca dos objetivos no relacionados → partir en un solo objetivo.

---

## Integración con otros namespaces

- **`pm:` (PMBOK)** — Scrum es el complemento **ágil/iterativo** del marco predictivo de PMBOK. El Sprint Backlog es el equivalente iterativo del WBS + Schedule de `pm:planning`: en lugar de una baseline de cronograma para todo el proyecto, se compromete el alcance de un Sprint. La velocity de Scrum alimenta los pronósticos de `pm:monitoring`; el capacity plan se relaciona con el Resource Management Plan de PMBOK.
- **`rm:` / `ba:` (requisitos / análisis de negocio)** — las historias del Product Backlog **derivan de los UC RUP** del proyecto (`docs/source/requisitos/historias-usuario/`, cada historia con su `UC-XXX`). `ba:requirements-analysis` produce y verifica las historias con INVEST; Sprint Planning las consume ya priorizadas. La trazabilidad historia→UC se mantiene viva durante la selección.
- **Ciclo THYROX (12 stages)** — Sprint Planning opera en **Stage 6 SCOPE** (qué entra al Sprint) y **Stage 8 PLAN EXECUTION** (cómo se ejecutará, en tareas). El incremento resultante se valida en Stage 9 PILOT/VALIDATE (Sprint Review) y se implementa en Stage 10 IMPLEMENT. La velocity y la Retrospective alimentan Stage 11 TRACK/EVALUATE y Stage 12 STANDARDIZE.

---

## Anti-patrones — Sprint Planning mal ejecutado

- **Sprint sin Goal, solo una lista de items** — sin objetivo único, el equipo no tiene criterio para negociar alcance a mitad de Sprint; el Goal es lo primero, no un adorno final.
- **Sobrecompromiso por encima de la velocity** — meter más puntos de los que el equipo históricamente completa garantiza spillover y un Sprint Goal incumplido; la velocity es el techo, no una sugerencia.
- **Items sin DoR forzados al Sprint** — comprometer una historia ambigua "para no perder el Sprint" traslada el refinamiento al medio de la ejecución, donde es más caro.
- **Estimar en horas en vez de story points** — las horas dan falsa precisión y se confunden con compromisos de fecha; los story points son relativos y absorben incertidumbre.
- **Push del Product Owner en vez de pull del equipo** — el equipo que ejecuta es quien estima y se compromete; un compromiso impuesto no es un compromiso.
- **Un item de 13 puntos comprometido entero** — un item del tamaño de un Sprint completo no deja margen para imprevistos; descomponer en planning o devolver al refinamiento.

---

## Artefacto esperado

- **Sprint Goal** — una frase, registrada al inicio del Sprint Backlog.
- **Sprint Backlog** — items seleccionados + tareas técnicas + estimación en story points.
- **Capacity plan** — días disponibles del equipo, ausencias conocidas, velocity de referencia.

---

## Siguiente paso

- Sprint Planning completo → ejecución del Sprint (Daily Scrum diario, actualización del Sprint Backlog).
- Backlog no listo (items sin DoR, sin priorizar) → `scrum-backlog-refinement` antes de re-planificar.
- Cierre del Sprint → Sprint Review (Stage 9) + Retrospective → nuevo `scrum-sprint-planning`.
