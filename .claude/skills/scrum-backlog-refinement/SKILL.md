---
name: scrum-backlog-refinement
description: "Use when keeping the Product Backlog healthy — splitting epics into stories, applying INVEST, estimating and ordering by value. scrum:backlog-refinement — desglosar épicas en historias Como/Quiero/Para, aplicar criterios INVEST, estimar en story points por planning poker, ordenar por valor y definir la Definition of Ready (DoR), manteniendo la trazabilidad historia→UC RUP."
allowed-tools: Read Glob Grep Bash Write Edit
effort: medium
disable-model-invocation: true
metadata:
  triggers: ["backlog refinement", "product backlog", "INVEST", "definition of ready", "user stories", "story splitting", "planning poker", "refinamiento de backlog"]
updated_at: 2026-06-02
---

# /scrum-backlog-refinement — Scrum: Product Backlog Refinement

> *"El refinamiento no es un evento, es una actividad continua. Un Product Backlog sano es aquel donde los items del tope están listos para entrar a un Sprint y los del fondo son grandes y vagos a propósito. Refinar es gastar esfuerzo ahora para que el Sprint Planning sea rápido y el compromiso, confiable. Una historia que no cabe en INVEST no es pequeña: es trabajo sin entender."*

Ejecuta el **Product Backlog Refinement** de Scrum: la actividad continua que mantiene el **Product Backlog** sano. Desglosa épicas en historias de usuario, las escribe en formato **Como/Quiero/Para**, aplica los criterios **INVEST**, las estima en **story points** mediante planning poker, las ordena por valor y define la **Definition of Ready (DoR)**. Cada historia deriva de un `UC-XXX` RUP del proyecto, manteniendo el puente con los requisitos. El output es un backlog donde el tope está listo para `scrum-sprint-planning`.

**THYROX Stage:** Stage 3 DIAGNOSE / Stage 6 SCOPE / Stage 7 DESIGN-SPECIFY.

**Outputs clave:** Product Backlog refinado · historias INVEST · Definition of Ready (DoR).

---

## Pre-condición

Requiere, antes de refinar:
- **Fuente de requisitos** — los Casos de Uso RUP del proyecto en `docs/source/requisitos/casos-uso/` y su catálogo (`docs/source/requisitos/catalogo-ucs.rst`). Cada historia debe poder anclarse a un `UC-XXX`.
- **Épicas o historias en bruto** — items grandes del Product Backlog que aún no están listos (sin INVEST, sin estimar, sin AC heredados del UC).
- **Product Owner disponible** — la priorización por valor y la aceptación de la DoR requieren la voz del Product Owner; el equipo refina, el PO ordena.

Si no hay UCs ni fuente de requisitos clara, no se inventan historias: se documenta el gap y se regresa a `ba:requirements-analysis` / `rm:elicitation`.

---

## Cuándo usar este paso

- De forma continua durante el Sprint (no como evento único): una sesión de refinamiento recurrente por Sprint para preparar los items del próximo.
- Cuando el tope del Product Backlog tiene items demasiado grandes (épicas, historias de 13+ puntos) que no caben en un Sprint.
- Cuando una historia llega a Sprint Planning sin cumplir DoR — se devuelve aquí en lugar de forzarla al Sprint.
- En el e-commerce Kaupamex: al desglosar una épica de checkout o catálogo en historias `historias-usuario/`, cada una trazada a su `UC-XXX`.

## Cuándo NO usar este paso

- Para comprometer un Sprint o construir el Sprint Backlog — eso es `scrum-sprint-planning`, no refinamiento.
- Para sincronizar el día o mover tarjetas del Sprint en curso — eso es `scrum-daily-standup`.
- Para elicitar requisitos desde cero sin un UC fuente — eso es trabajo de `ba:elicitation` / `rm:elicitation`; el refinamiento parte de requisitos ya existentes.

---

## Actividades

| Actividad | Output | Técnicas clave |
|-----------|--------|----------------|
| **1. Desglosar épicas** | Historias de tamaño manejable | Story splitting por workflow, por reglas de negocio, por variantes de dato (ver patrones abajo) |
| **2. Escribir historias Como/Quiero/Para** | Historias en formato canónico | "Como `<actor>` quiero `<capacidad>` para `<valor>`"; AC heredados del `UC-XXX` |
| **3. Aplicar INVEST** | Historias que pasan los 6 criterios | Revisión item por item contra Independent, Negotiable, Valuable, Estimable, Small, Testable |
| **4. Estimar relativo** | Story points por historia | Planning poker, Fibonacci 1·2·3·5·8·13; comparación relativa contra historias de referencia |
| **5. Ordenar por valor** | Backlog priorizado | Ordenamiento por valor de negocio + riesgo + dependencias; el PO decide el orden |
| **6. Definir / verificar DoR** | Items del tope que cumplen DoR | Checklist de Definition of Ready aplicado al tope del backlog |

---

## INVEST — los seis criterios

Cada historia del tope del backlog debe cumplir los **seis**. Si falla uno, no está lista.

| Letra | Criterio | Qué verificar | Síntoma de falla |
|-------|----------|---------------|------------------|
| **I** | Independent | La historia se puede construir y entregar sin depender de otra del mismo Sprint | "No se puede hacer hasta que esté la otra" |
| **N** | Negotiable | Describe el qué y el porqué, deja el cómo abierto a la conversación | Historia que prescribe la implementación al detalle |
| **V** | Valuable | Entrega valor observable a un actor (no una tarea técnica interna) | "Refactorizar el repositorio de pedidos" como historia |
| **E** | Estimable | El equipo entiende lo suficiente para estimarla | Nadie sabe estimar → falta refinamiento o spike |
| **S** | Small | Cabe holgadamente en un Sprint (idealmente ≤ 8 puntos) | 13 puntos o más → desglosar |
| **T** | Testable | Tiene criterios de aceptación verificables (heredados del `UC-XXX`) | "Que funcione bien" sin AC concretos |

Una historia que falla **E** o **S** se devuelve a desglose; una que falla **T** se trabaja con el Product Owner hasta tener AC concretos (que en este proyecto se heredan del UC RUP).

---

## Story splitting — patrones de desglose

Una épica se parte en historias verticales (cada una entrega valor end-to-end), no en capas técnicas:

| Patrón | Cómo | Ejemplo Kaupamex |
|--------|------|------------------------|
| **Por pasos del workflow** | Una historia por etapa del flujo | Checkout: ver carrito → ingresar envío → pagar → confirmar |
| **Por reglas de negocio** | Separar la variante simple de las reglas complejas | "Pagar con tarjeta" antes de "pagar en cuotas (MSI)" |
| **Por variaciones de dato** | Caso común primero, casos especiales después | "Producto con stock" antes de "producto agotado / backorder" |
| **Por operación CRUD** | Separar crear/leer/actualizar/borrar | Catálogo: listar productos antes de filtrar y ordenar |
| **Spike de investigación** | Cuando no es estimable, una historia para reducir incertidumbre | Investigar API de Mercado Pago antes de estimar el pago |

Regla: cada historia resultante debe seguir siendo **Valuable** y **Testable** por sí sola. Partir por capas técnicas (backend / frontend) viola INVEST porque ninguna mitad entrega valor sola.

---

## Definition of Ready (DoR)

La DoR es el contrato de entrada al Sprint: un item solo es candidato a `scrum-sprint-planning` si cumple **todos**:

1. **Historia en formato Como/Quiero/Para** con actor, capacidad y valor explícitos.
2. **Trazabilidad a un `UC-XXX`** — la historia cita su UC origen (campo `:uc_origen:` en `historias-usuario/`).
3. **Criterios de aceptación verificables** — heredados del UC RUP, no inventados.
4. **Estimada en story points** — con un valor Fibonacci acordado por el equipo (no 13+ sin desglosar).
5. **Cumple INVEST** — los seis criterios verificados.
6. **Dependencias identificadas** — si hay alguna, está documentada y no bloquea el Sprint.

La DoR es el espejo de la Definition of Done: la DoR controla qué entra, la DoD qué se considera terminado. Sin DoR explícita, "listo" es opinión y el Sprint Planning negocia sobre arena.

---

## Puente con los UC RUP — trazabilidad historia→UC

El Product Backlog de este proyecto **no nace de cero**: cada historia deriva de un Caso de Uso RUP ya documentado.

- Los **UC RUP** (`docs/source/requisitos/casos-uso/`) documentan *el qué funcional* con precisión técnica: contrato HTTP, diagramas de secuencia, AC detallados.
- Las **historias de usuario** (`docs/source/requisitos/historias-usuario/`) documentan *el valor para el actor* en lenguaje de negocio, orientadas a la planificación ágil.
- El **puente es bidireccional**: la historia cita su `UC-XXX` en `:uc_origen:` y hereda sus AC; el UC puede listar las historias derivadas en su sección de trazabilidad.

Durante el refinamiento, esta trazabilidad es obligatoria: una historia sin UC origen es una historia sin requisito que la respalde. Si el refinamiento detecta que el UC fuente está incompleto o mal especificado, **se corrige o completa el UC** (no se continúa sobre un requisito incorrecto) antes de derivar la historia.

---

## Quality gates — ¿backlog refinado?

**Refinamiento aprobado (todos los siguientes):**
1. **Los items del tope del backlog cumplen INVEST + DoR** — listos para entrar al próximo Sprint Planning sin retrabajo.
2. **Trazabilidad historia→UC explícita** — cada historia del tope cita su `UC-XXX` origen y hereda sus criterios de aceptación.
3. Las épicas grandes están desglosadas en historias verticales (cada una Valuable y Testable por sí sola).
4. Cada historia del tope tiene una estimación Fibonacci acordada por el equipo (ninguna 13+ sin descomponer).
5. El backlog está ordenado por valor de negocio por el Product Owner.

**Requiere más refinamiento:**
- Hay items de 13+ puntos en el tope → desglosar antes de que lleguen a Sprint Planning.
- Una historia no es estimable → falta entendimiento; refinar más o crear un spike.
- Una historia no cita UC origen → trazar al requisito o documentar el gap en `ba:requirements-analysis`.
- El tope del backlog tiene historias sin AC verificables → trabajar con el PO hasta tener Definition of Ready.

---

## Integración con otros namespaces

- **`pm:` (PMBOK)** — Scrum es el complemento **ágil/iterativo** del marco predictivo de PMBOK. El Product Backlog refinado es el equivalente vivo y reordenable del Scope baseline + WBS de `pm:planning`: en vez de un alcance congelado al inicio, se mantiene un backlog ordenado que absorbe cambios. La descomposición de épicas en historias es la versión ágil de la descomposición WBS; los story points alimentan los pronósticos de esfuerzo que `pm:monitoring` usa para forecast.
- **`rm:` / `ba:` (requisitos / análisis de negocio)** — las historias **derivan de los UC RUP** del proyecto (`docs/source/requisitos/casos-uso/` → `historias-usuario/`, cada historia con su `UC-XXX`). `ba:requirements-analysis` y `rm:specification` producen y verifican los UC con sus AC; el refinamiento los consume y los traduce a historias INVEST sin perder trazabilidad. Si el refinamiento detecta un UC incompleto, lo escala a `rm:elicitation` / `ba:elicitation` para completarlo.
- **`scrum:` (mismo namespace)** — el refinamiento alimenta a `scrum-sprint-planning` (entrega items que cumplen DoR) y se relaciona con `scrum-definition-of-done` (DoR de entrada ↔ DoD de salida). La `scrum-retrospective` puede detectar que el refinamiento es insuficiente (muchos items vuelven al backlog) y mejorar la cadencia.
- **Ciclo THYROX (12 stages)** — el refinamiento opera en **Stage 3 DIAGNOSE** (entender el problema y desglosar épicas), **Stage 6 SCOPE** (ordenar y delimitar qué entra al producto) y **Stage 7 DESIGN-SPECIFY** (especificar AC y DoR por historia). Su output prioritizado entra a Stage 8 PLAN EXECUTION vía Sprint Planning; la velocity y el flujo del backlog alimentan Stage 11 TRACK/EVALUATE y la estabilización de Stage 12 STANDARDIZE.

---

## Anti-patrones — refinamiento mal ejecutado

- **Historias técnicas sin valor** — "Crear tabla de pedidos" o "Refactorizar el servicio de pago" no son historias: violan **Valuable**. La historia describe valor para un actor; las tareas técnicas viven dentro del Sprint Backlog, no en el Product Backlog.
- **Partir por capas en vez de vertical** — desglosar una épica en "el backend" y "el frontend" deja dos mitades que no entregan valor solas; partir siempre en historias verticales end-to-end.
- **Historias de 13+ puntos en el tope** — un item del tamaño de un Sprint completo no es refinamiento terminado; desglosar antes de que llegue a Sprint Planning.
- **Refinar todo el backlog al mismo detalle** — gastar esfuerzo refinando el fondo del backlog (que probablemente cambie) es desperdicio; el fondo es grande y vago a propósito, solo el tope se refina al detalle.
- **Historias sin UC origen** — inventar historias sin anclarlas a un `UC-XXX` rompe la trazabilidad y produce trabajo sin requisito que lo respalde; toda historia deriva de un UC.
- **AC genéricos no verificables** — "que funcione" o "que sea rápido" no son criterios de aceptación; los AC se heredan del UC RUP y deben ser testables (criterio **Testable**).
- **DoR implícita** — sin una Definition of Ready explícita, "listo" es opinión y cada Sprint Planning re-discute qué significa estar listo; la DoR es un contrato escrito.

---

## Artefacto esperado

- **Product Backlog refinado** — historias ordenadas por valor, las del tope listas para el próximo Sprint.
- **Historias INVEST** — en `docs/source/requisitos/historias-usuario/`, formato Como/Quiero/Para, cada una con su `:uc_origen:` y AC heredados.
- **Definition of Ready (DoR)** — checklist explícito de entrada al Sprint, acordado por equipo y Product Owner.

---

## Siguiente paso

- Backlog refinado (tope cumple INVEST + DoR) → `scrum-sprint-planning` para comprometer el próximo Sprint.
- UC fuente incompleto o ausente → `rm:elicitation` / `ba:requirements-analysis` para completarlo antes de derivar historias.
- DoR repetidamente incumplida en planning → `scrum-retrospective` para ajustar la cadencia y profundidad del refinamiento.
