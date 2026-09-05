---
name: scrum-retrospective
description: "Use when a Sprint ends and the team must inspect its own process and teamwork to improve. scrum:retrospective — run a Start/Stop/Continue retrospective in a blameless space, produce at least one concrete improvement action with an owner and a date, and feed lessons into the project's lessons-learned memory."
allowed-tools: Read Glob Grep Bash Write Edit
effort: medium
disable-model-invocation: true
metadata:
  triggers: ["retrospective", "retrospectiva", "start stop continue", "mejora continua del equipo", "acciones de mejora", "lecciones aprendidas", "blameless retrospective"]
updated_at: 2026-06-02
---

# /scrum-retrospective — Scrum: Sprint Retrospective (Ceremonia)

> *"The Retrospective inspects the team and its process, not the product. It is the engine of continuous improvement: a Sprint that ends without at least one concrete, owned action did not learn anything. Psychological safety is the precondition — people only name the real problem when no one gets blamed for it."*

Ejecuta la ceremonia **Sprint Retrospective**: la inspección del **proceso y del equipo** —no del producto— al cierre del Sprint. El equipo revisa cómo trabajó (colaboración, herramientas, impedimentos, Definition of Done) y genera **acciones de mejora concretas con dueño y fecha**. Es el motor de mejora continua de Scrum, y el puente con la **memoria de lecciones aprendidas** del proyecto. El resultado es al menos una acción accionable que cambia cómo trabaja el equipo en el próximo Sprint.

**THYROX Stage:** Stage 11 TRACK-EVALUATE / Stage 12 STANDARDIZE.

**Outputs clave:** acciones de mejora (con dueño + fecha) · lecciones registradas en la memoria del proyecto.

---

## Pre-condición

Requiere:
- Un Sprint que cierra, idealmente tras la **Sprint Review** (primero se inspecciona el producto, luego el proceso).
- El **equipo completo** presente: Development Team, Scrum Master y Product Owner — quienes vivieron el Sprint.
- Un **clima seguro** (blameless): el objetivo es mejorar el sistema de trabajo, no señalar culpables.
- Acceso a las **acciones de la retrospectiva anterior**, para revisar si se cumplieron antes de generar nuevas.

---

## Cuándo usar este paso

- Al final de cada Sprint, después de la Sprint Review y antes del próximo Sprint Planning.
- Cuando el equipo necesita convertir frustraciones, impedimentos recurrentes o aciertos en cambios concretos de su forma de trabajar.
- Cuando un patrón sistémico (deuda, fricción de proceso, fallos repetidos) merece una lección registrada en la memoria del proyecto.

## Cuándo NO usar este paso

- Para inspeccionar el **producto** o recoger feedback de stakeholders — eso es `scrum:sprint-review`, no la Retrospective.
- Como sesión de quejas sin acciones — una retro sin al menos una acción accionable con dueño no cumplió su función.
- Como tribunal para asignar culpas — eso destruye la seguridad psicológica y garantiza que los problemas reales no vuelvan a nombrarse.
- Para re-planificar tareas del próximo Sprint — eso es `scrum:sprint-planning`; la retro mejora el *cómo*, no define el *qué*.

---

## Formato — Start / Stop / Continue

El formato canónico ordena la conversación en tres columnas. Es intercambiable con la variante "qué salió bien / qué mejorar / acciones", siempre que termine en acciones:

| Columna | Pregunta | Ejemplo (Kaupamex) |
|---------|----------|--------------------------|
| **Start** (empezar) | ¿Qué deberíamos empezar a hacer? | "Pair programming en los módulos de pago" |
| **Stop** (dejar) | ¿Qué deberíamos dejar de hacer? | "Dejar de comprometer items sin Definition of Ready" |
| **Continue** (seguir) | ¿Qué funcionó y debemos mantener? | "Seguir el walk-the-board del Daily, que destapó bloqueos temprano" |

Variante equivalente:

| Bloque | Pregunta |
|--------|----------|
| **Qué salió bien** | Lo que funcionó y vale la pena reforzar |
| **Qué mejorar** | Lo que generó fricción o no funcionó |
| **Acciones** | Cambios concretos a implementar, con dueño y fecha |

Cualquier formato sirve **si converge en acciones**: la conversación es el medio, las acciones accionables son el output.

---

## Actividades

| Actividad | Output | Cómo |
|-----------|--------|------|
| **1. Revisar acciones de la retro anterior** | Estado de cada acción previa (hecha / no / en curso) | Abrir las acciones del Sprint pasado; cerrar las cumplidas, reabrir las que no |
| **2. Recoger datos del Sprint** | Imagen compartida de cómo fue el Sprint | Start/Stop/Continue o "bien/mejorar"; hechos antes que opiniones |
| **3. Generar insights** | Causas raíz de los patrones detectados | Agrupar temas; preguntar "por qué" hasta la causa sistémica, no la persona |
| **4. Decidir acciones de mejora** | ≥1 acción accionable con dueño + fecha | Priorizar 1-3 acciones realizables en el próximo Sprint; asignar dueño concreto |
| **5. Registrar lecciones** | Lección en la memoria del proyecto | Documentar el patrón y la acción en `lecciones-aprendidas/` (ver abajo) |

---

## Acciones de mejora — de insight a compromiso

Una retro que no produce acciones es una sesión de desahogo. Cada acción debe tener:

| Campo | Obligatorio | Ejemplo |
|-------|-------------|---------|
| **Descripción** | Sí | "Añadir verificación de Definition of Ready al refinamiento" |
| **Dueño** (quién la lleva) | Sí | Un developer o el Scrum Master, nombrado |
| **Fecha objetivo** | Sí | Antes del cierre del próximo Sprint |
| **Señal de éxito** | Recomendado | "0 items sin DoR comprometidos en el próximo Sprint" |
| **Estado** | Sí | Abierta / En progreso / Cerrada |

Limitar a **1-3 acciones** por retro: comprometer diez garantiza que ninguna se haga. Las acciones se **revisan al inicio de la siguiente retro** (Actividad 1) — ese loop es lo que hace que la mejora sea continua y no decorativa.

---

## Puente con la memoria de lecciones aprendidas

La retrospectiva no se queda en el equipo: los patrones sistémicos y sus acciones se registran en la **memoria de lecciones del proyecto** para que sobrevivan al Sprint y estén disponibles en sesiones futuras.

- **Ubicación canónica:** `docs/source/gestion/pm/docs/lecciones-aprendidas/`.
- **Qué registrar:** patrones recurrentes, causas raíz de fricción de proceso, fallos que se repiten entre Sprints, y la acción que los corrige. No cada comentario, sino la lección con valor de retrieval.
- **Formato:** archivo RST con la convención del proyecto (`:categoria:`, `:condicion:` como clave de retrieval, secciones Contexto / Qué Pasó / Causa Raíz / Solución / Regla / Cuándo Aplica). Una lección bien indexada se recupera con un `grep` por su `condicion`.
- **Por qué importa:** sin este registro, la misma fricción se redescubre Sprint tras Sprint; con él, la retro alimenta la estandarización del proyecto.

---

## Quality gates

La Retrospective está bien ejecutada solo si se cumplen TODOS:

1. **≥1 acción accionable con dueño** — la retro produce al menos una acción de mejora concreta y realizable, con una persona responsable nombrada y una fecha objetivo. Una retro sin acción no cumplió su función.
2. **Las acciones se revisan en la siguiente retro** — cada retrospectiva abre revisando el estado de las acciones de la anterior; sin ese loop, las acciones se acumulan sin efecto.
3. **Clima seguro (sin culpa)** — la sesión inspecciona el sistema de trabajo, no a las personas; nadie es señalado como culpable. Si la retro se vuelve un tribunal, el gate falla.
4. **Lecciones sistémicas registradas** — los patrones con valor más allá del Sprint quedan en `lecciones-aprendidas/`, no solo en la memoria del equipo.

---

## Integración con otros namespaces

- **`pm:` (PMBOK)** — la Retrospective es el motor iterativo de las **Lessons Learned** de PMBOK: alimenta `pm:monitoring` (acciones correctivas/preventivas sobre el proceso) y, al cierre, `pm:closing` (registro de lecciones aprendidas del proyecto). Donde PMBOK registra lecciones al final de fase, Scrum las registra cada Sprint.
- **`pps:` / `lean:` (mejora continua)** — la retro **es** mejora continua: el análisis de causa raíz de los patrones recurrentes es Ishikawa/5-porqués al estilo `pps:analyze` y `lean:analyze`; las acciones eliminan desperdicio de proceso (esperas, retrabajo, fricción). La retro es el evento donde el equipo hace kaizen sobre su propio sistema de trabajo.
- **`pdca:` (PDCA)** — la retro es el **Check + Act** sobre el *proceso* del Sprint: inspecciona cómo se trabajó (Check) y decide cambios concretos (Act) que se prueban en el próximo Sprint (Plan/Do). Es el cierre del ciclo PDCA a nivel de equipo, complementario a la Review que hace Check/Act sobre el *producto*.
- **Ciclo THYROX** — la retro vive en **Stage 11 TRACK-EVALUATE** (se evalúa cómo trabajó el equipo y se mide la mejora) y conecta con **Stage 12 STANDARDIZE** (las acciones y lecciones que funcionan se estandarizan e incorporan a la forma de trabajar y a la Definition of Done). Es el puente entre evaluar y consolidar el aprendizaje.

---

## Anti-patrones

- **Retro sin acciones** — terminar la sesión con una lista de quejas y ningún cambio concreto convierte la mejora continua en desahogo continuo; sin acción, nada cambia.
- **Acciones sin dueño ni fecha** — "deberíamos mejorar la comunicación" no es una acción; sin responsable y fecha, nadie la lleva y reaparece idéntica la próxima retro.
- **No revisar las acciones anteriores** — generar acciones nuevas sin verificar las viejas garantiza que se acumulen sin cumplirse; el loop de revisión es lo que da efecto a la retro.
- **Buscar culpables** — convertir la retro en un tribunal rompe la seguridad psicológica; la próxima vez nadie nombrará el problema real y la mejora muere.
- **Diez acciones por retro** — comprometer demasiadas acciones garantiza que ninguna se complete; 1-3 realizables superan a diez aspiracionales.
- **Lecciones que no salen de la sala** — no registrar los patrones sistémicos en `lecciones-aprendidas/` condena al proyecto a redescubrir la misma fricción Sprint tras Sprint.
- **Mezclar producto y proceso** — discutir features o feedback de usuarios en la retro invade el territorio de la Sprint Review; la retro inspecciona el *cómo*, no el *qué*.

---

## Artefacto esperado

- **Acciones de mejora** — 1-3 acciones accionables, cada una con dueño, fecha objetivo y señal de éxito, con su estado.
- **Registro de revisión** — estado de cierre de las acciones de la retrospectiva anterior.
- **Lecciones registradas** — patrones sistémicos documentados en `docs/source/gestion/pm/docs/lecciones-aprendidas/` con la convención del proyecto.

---

## Siguiente paso

- Retro completa → `scrum:sprint-planning` del próximo Sprint, arrancando con las acciones de mejora vivas.
- Acción que requiere cambiar la Definition of Done → `scrum:definition-of-done` para incorporar el criterio nuevo.
- Lección sistémica de alto impacto → estandarización en el proyecto (Stage 12 STANDARDIZE) e insumo de `pm:closing`.
