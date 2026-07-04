---
name: scrum-daily-standup
description: "Use when the Development Team needs to synchronize daily during a Sprint and inspect progress toward the Sprint Goal. scrum:daily-standup — run the 15-min Daily Scrum, update the Sprint Backlog and burndown, and escalate impediments with an owner and a date."
allowed-tools: Read Glob Grep Bash Write Edit
effort: medium
disable-model-invocation: true
metadata:
  triggers: ["daily standup", "daily scrum", "stand-up diario", "sincronización diaria", "burndown del sprint"]
updated_at: 2026-06-02
---

# /scrum-daily-standup — Scrum: Daily Scrum (Ceremonia)

> *"The Daily Scrum is not a status meeting for the manager. It is the moment when the developers, and only the developers, re-plan their next day of work to maximize the probability of meeting the Sprint Goal. Fifteen minutes, every day, same time, same place."*

Ejecuta la ceremonia **Daily Scrum**: la sincronización diaria de 15 minutos del Development Team durante el Sprint. El equipo inspecciona el progreso hacia el **Sprint Goal**, replanifica el trabajo del día, actualiza el **Sprint Backlog** y el **burndown**, y escala los impedimentos. No es un reporte de estado al manager: es una conversación entre developers para auto-organizarse.

**THYROX Stage:** Stage 10 IMPLEMENT / Stage 11 TRACK-EVALUATE.

**Outputs clave:** impedimentos registrados (con dueño + fecha) · burndown actualizado · plan del día acordado.

---

## Pre-condición

Requiere:
- Un Sprint en curso con un **Sprint Goal** claro y un **Sprint Backlog** vivo.
- El Development Team disponible a la misma hora cada día (timebox fijo).
- Acceso al tablero/burndown del Sprint para actualizarlo en el momento.

---

## Cuándo usar este paso

- Una vez por día durante todo el Sprint, a la misma hora y lugar.
- Cuando el equipo necesita re-planificar el día a la luz de lo ocurrido ayer.
- Cuando un developer necesita visibilizar un impedimento que bloquea el avance hacia el Sprint Goal.

## Cuándo NO usar este paso

- Como reporte de estado para un manager o stakeholder externo — eso degrada la ceremonia a vigilancia y rompe la auto-organización (usar `scrum:sprint-review` para stakeholders).
- Para resolver el impedimento en la misma reunión — el Daily detecta y escala; la resolución técnica se hace después, fuera del timebox, con quienes corresponda.
- Para re-estimar el Product Backlog o discutir trabajo futuro — eso es refinamiento, no Daily Scrum.

---

## Estructura — las tres preguntas

Cada developer responde, en función del **Sprint Goal**, no de su agenda personal:

| Pregunta | Propósito | Anti-uso |
|----------|-----------|----------|
| **¿Qué hice ayer** que ayudó al equipo a acercarse al Sprint Goal? | Inspeccionar progreso real, no horas trabajadas | Recitar tareas sin relación con el Goal |
| **¿Qué haré hoy** para ayudar al equipo a acercarse al Sprint Goal? | Replanificar el día y comprometer el siguiente paso | Anunciar trabajo que nadie puede ver en el tablero |
| **¿Veo algún impedimento** que me bloquee a mí o al equipo? | Hacer visible lo que frena el avance | Callar el bloqueo "para no molestar" |

> El foco es el **Sprint Goal**. Si las tres preguntas no se anclan al Goal, el Daily se convierte en un parte de horas. Equipos maduros pueden reemplazar las tres preguntas por una inspección directa del tablero columna a columna (walk the board), siempre que el resultado sea el mismo: un plan del día que maximiza la probabilidad de cumplir el Goal.

---

## Actividades

| Actividad | Output | Cómo |
|-----------|--------|------|
| **1. Inspeccionar el progreso hacia el Sprint Goal** | Lectura compartida de cuán cerca está el equipo del Goal | Recorrer el tablero o las tres preguntas; comparar lo planeado vs lo hecho |
| **2. Replanificar el día** | Plan del día acordado entre developers | Reasignar foco, emparejar (pairing) donde haya riesgo, mover el trabajo de mayor valor para el Goal |
| **3. Actualizar el Sprint Backlog** | Estados de los items al día | Mover tarjetas (To Do → In Progress → Done), añadir trabajo descubierto, retirar lo que ya no aporta al Goal |
| **4. Actualizar el burndown** | Gráfico de trabajo restante refrescado | Recalcular el trabajo pendiente; comparar la línea real contra la ideal |
| **5. Registrar y escalar impedimentos** | Lista de impedimentos con dueño + fecha | Anotar cada bloqueo; asignar un responsable de removerlo y una fecha objetivo |

---

## Lectura del burndown — qué inspeccionar

La actualización del burndown no es decorativa: es el observable que dispara decisiones.

| Señal en el burndown | Interpretación | Acción en el Daily |
|----------------------|----------------|--------------------|
| Línea real **por encima** de la ideal | El equipo va retrasado respecto al Goal | Replanificar foco; ¿hay impedimento oculto? ¿alcance que negociar con el Product Owner? |
| Línea **plana** varios días | El trabajo no se está cerrando (todo "en progreso") | Limitar WIP; emparejar para terminar antes de empezar lo nuevo |
| Línea **por debajo** de la ideal | Avance más rápido de lo previsto | ¿Adelantar items? ¿el equipo subestimó? Nota para la retrospectiva |
| Saltos hacia **arriba** | Apareció trabajo nuevo (scope creep dentro del Sprint) | Verificar que el nuevo trabajo sirve al Sprint Goal; si no, escalar al Product Owner |

---

## Gestión de impedimentos

Cada impedimento registrado en el Daily debe tener:

| Campo | Obligatorio | Ejemplo |
|-------|-------------|---------|
| **Descripción** | Sí | "Entorno de QA caído, bloquea la verificación de 3 items" |
| **Dueño** (quién lo remueve) | Sí | Scrum Master / un developer nombrado |
| **Fecha objetivo** de remoción | Sí | 2026-06-03 |
| **Impacto en el Sprint Goal** | Sí | "Bloquea el cierre de la épica de checkout" |
| **Estado** | Sí | Abierto / En progreso / Removido |

Un impedimento sin dueño y sin fecha **no está gestionado** — solo está anunciado. El Scrum Master facilita la remoción, pero el dueño es siempre una persona concreta.

---

## Quality gates

El Daily Scrum está bien ejecutado solo si se cumplen TODOS:

1. **Foco en el Sprint Goal** — la conversación gira en torno a acercarse al Goal, no en reportar estatus a un manager. Si alguien presente convierte la reunión en rendición de cuentas hacia arriba, el gate falla.
2. **Impedimentos con dueño y fecha** — cada bloqueo registrado tiene un responsable nombrado y una fecha objetivo de remoción. Ningún impedimento queda "flotando".
3. **Timebox de 15 minutos** — la ceremonia no excede los 15 minutos. Las discusiones técnicas profundas se sacan del Daily ("parking lot") y se resuelven después con quienes correspondan.
4. **Sprint Backlog y burndown actualizados** — al terminar el Daily, el tablero y el gráfico reflejan el estado real del trabajo, no el de ayer.

---

## Integración con otros namespaces

- **`pm:` (PMBOK)** — el Daily alimenta el proceso de **Monitoring & Controlling** (`pm:monitoring`): el burndown es la fuente del trabajo restante y los impedimentos escalados son insumo del Issue Log. Al cerrar el Sprint, el aprendizaje fluye hacia `pm:closing`.
- **`pps:` / `lean:` (mejora continua)** — la actualización diaria del burndown es una forma de control visual al estilo **Lean** (gestión a la vista); el Daily limita el WIP y expone cuellos de botella tal como un sistema pull. Los impedimentos recurrentes son síntomas que `lean:analyze` y `pps:analyze` ayudan a llevar a causa raíz.
- **`pdca:` (PDCA)** — el Daily es un micro-ciclo **Check** diario sobre el **Do** del Sprint: se inspecciona el progreso (Check) y se replanifica el día (Act ligero). La retrospectiva (`scrum:retrospective`) recoge los Check/Act que exceden el día.
- **Ciclo THYROX** — el Daily vive en el corazón de **Stage 10 IMPLEMENT** (se ejecuta el trabajo planificado) con un pie en **Stage 11 TRACK-EVALUATE** (se inspecciona y mide el progreso cada día). Es el latido que conecta ejecución y seguimiento.

---

## Anti-patrones

- **Status report al manager** — convertir el Daily en una rendición de cuentas hacia arriba mata la auto-organización: los developers hablan para el jefe, no entre ellos, y dejan de re-planificar de verdad.
- **Resolver el impedimento dentro del timebox** — arrastrar al equipo a un debugging colectivo de 40 minutos rompe los 15 minutos y secuestra a quienes no estaban involucrados; el Daily detecta, no resuelve.
- **Impedimentos sin dueño** — anunciar "está caído QA" sin nombrar responsable ni fecha garantiza que nadie lo remueva; el bloqueo reaparece idéntico al día siguiente.
- **Burndown que no se toca** — si el gráfico queda congelado, el equipo pierde su único observable temprano de retraso y descubre el problema recién en la Sprint Review.
- **Daily sin Sprint Goal** — sin un Goal claro, las tres preguntas degeneran en una lista de tareas inconexas y el equipo optimiza actividad en vez de resultado.
- **Recitar tareas Jira en vez de hablar del Goal** — leer el tablero en voz alta no es inspeccionar el progreso; el foco debe ser cuánto se acercó (o alejó) el equipo del Sprint Goal.
