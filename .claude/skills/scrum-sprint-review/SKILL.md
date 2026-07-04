---
name: scrum-sprint-review
description: "Use when a Sprint ends and the Development Team must demonstrate the Done Increment to stakeholders and collect feedback. scrum:sprint-review — show only Done work, capture stakeholder feedback as Product Backlog items, and update the backlog so the next Sprint reflects what was learned."
allowed-tools: Read Glob Grep Bash Write Edit
effort: medium
disable-model-invocation: true
metadata:
  triggers: ["sprint review", "demo del sprint", "incremento done", "stakeholder feedback", "revisión del incremento", "product backlog update"]
updated_at: 2026-06-02
---

# /scrum-sprint-review — Scrum: Sprint Review (Ceremonia)

> *"The Sprint Review is an inspection of the product, not the process. The team and the stakeholders look at what was actually built — the Done Increment — and decide together what to do next. It is a working session, not a presentation: feedback walks out as backlog, not as applause."*

Ejecuta la ceremonia **Sprint Review**: al final del Sprint, el equipo demuestra el **Increment** "Done" a los stakeholders, recoge su feedback y, con él, **actualiza el Product Backlog**. Es una inspección del **producto** —qué se construyó y qué valor entrega—, no del proceso del equipo (eso es la Retrospective). El resultado es un Product Backlog ajustado a lo que se aprendió viendo el producto funcionar.

**THYROX Stage:** Stage 9 PILOT/VALIDATE / Stage 11 TRACK-EVALUATE.

**Outputs clave:** Increment demostrado · feedback de stakeholders capturado · Product Backlog actualizado.

---

## Pre-condición

Requiere:
- Un **Increment** que cumple la **Definition of Done** — solo lo "Done" se muestra (ver `scrum:definition-of-done`).
- El **Sprint Goal** del Sprint que cierra, para enmarcar qué se prometió vs qué se logró.
- **Stakeholders reales** presentes: Product Owner, usuarios, sponsor o quien represente la demanda del producto — no solo el equipo.
- Un entorno donde demostrar el producto funcionando (no diapositivas de lo que "estaría" hecho).

Sin un Increment Done, no hay Sprint Review en sentido pleno: se muestra lo que sí cumple DoD y el resto vuelve al backlog.

---

## Cuándo usar este paso

- Al final de cada Sprint, antes de la Retrospective, para inspeccionar el producto con los stakeholders.
- Cuando hay que decidir, con feedback real, qué entra al Product Backlog y cómo se re-prioriza para el próximo Sprint.
- En PracticaYoruba: para demostrar un incremento del checkout, catálogo o panel de administración a quien representa al comprador o al negocio, y recoger qué ajustar.

## Cuándo NO usar este paso

- Para inspeccionar **cómo trabajó el equipo** (clima, proceso, impedimentos sistémicos) — eso es `scrum:retrospective`, no Sprint Review.
- Para mostrar trabajo a medias o que no cumple la Definition of Done — eso engaña al stakeholder sobre el estado real del producto.
- Como demo unilateral sin diálogo — si los stakeholders solo miran y aplauden, no hubo inspección; el feedback es el output, no la cortesía.
- Para re-planificar el detalle del próximo Sprint — eso es `scrum:sprint-planning`; la Review alimenta el backlog que ese planning consumirá.

---

## Estructura de la sesión

| Momento | Qué ocurre | Quién conduce |
|---------|------------|---------------|
| **1. Encuadre** | Recordar el Sprint Goal y qué se prometió este Sprint | Product Owner |
| **2. Estado del backlog** | Qué items se completaron (Done) y cuáles no, y por qué | Product Owner / equipo |
| **3. Demostración del Increment** | Mostrar el producto funcionando, no contar lo hecho | Development Team |
| **4. Feedback de stakeholders** | Diálogo: qué falta, qué cambió en el mercado, qué priorizar | Stakeholders + equipo |
| **5. Revisión de backlog y próximos pasos** | Ajustar el Product Backlog con lo recogido; re-priorizar | Product Owner |

La Review es **colaborativa**: el equipo demuestra, los stakeholders reaccionan, y el Product Owner traduce esa reacción en cambios concretos al backlog.

---

## Actividades

| Actividad | Output | Cómo |
|-----------|--------|------|
| **1. Verificar Done antes de mostrar** | Lista de items que cumplen DoD | Contrastar cada item contra la Definition of Done; lo no-Done no se demuestra |
| **2. Demostrar el Increment** | Producto funcionando ante stakeholders | Demo en vivo sobre datos/entorno reales; mostrar el flujo, no diapositivas |
| **3. Recoger feedback** | Notas de feedback atribuidas a su origen | Escuchar a cada stakeholder; preguntar por valor, prioridad y gaps |
| **4. Convertir feedback en backlog items** | Nuevos items / cambios en el Product Backlog | Cada feedback relevante se escribe como item con su contexto, no se pierde en acta |
| **5. Re-priorizar el Product Backlog** | Backlog actualizado y reordenado | El Product Owner ajusta prioridades a la luz de lo aprendido para el próximo planning |

---

## Captura de feedback — de comentario a backlog item

El feedback que no se registra como item del Product Backlog **se pierde**. Cada comentario relevante se traduce:

| Campo | Obligatorio | Ejemplo |
|-------|-------------|---------|
| **Descripción** | Sí | "El comprador quiere ver el costo de envío antes de iniciar el pago" |
| **Origen** (qué stakeholder) | Sí | Representante del negocio / usuario piloto |
| **Valor / motivación** | Sí | "Reduce abandono de carrito en el checkout" |
| **Prioridad sugerida** | Sí | Alta / media / baja — la fija el Product Owner |
| **Trazabilidad** | Recomendado | UC-XXX o historia relacionada, si aplica |

Un "buena idea, lo tenemos en cuenta" sin item creado equivale a no haber recogido el feedback.

---

## Definition of Done — la línea que separa lo que se muestra

Solo el trabajo que cumple la **Definition of Done** se demuestra como parte del Increment. Mostrar trabajo "casi listo" como si estuviera Done:

- da al stakeholder una imagen falsa del estado del producto,
- infla la percepción de avance y distorsiona la velocity,
- traslada al próximo Sprint un trabajo que se creyó terminado.

Si un item comprometido no llegó a Done, se dice explícitamente y vuelve al Product Backlog para re-priorizarse — no se disfraza en la demo. Ver `scrum:definition-of-done`.

---

## Quality gates

La Sprint Review está bien ejecutada solo si se cumplen TODOS:

1. **Solo se muestra trabajo que cumple la Definition of Done** — el Increment demostrado es Done; lo no-Done se declara y vuelve al backlog, no se exhibe.
2. **Feedback capturado como items de backlog** — cada comentario relevante de los stakeholders termina como item nuevo o cambio en el Product Backlog, con origen y motivación, no como nota suelta en un acta.
3. **Participan stakeholders reales** — están presentes quienes representan la demanda del producto (Product Owner, usuarios, sponsor), no solo el equipo de desarrollo demostrándose a sí mismo.
4. **El Product Backlog queda actualizado** — al cerrar la Review, el backlog refleja lo aprendido y está re-priorizado para alimentar el próximo Sprint Planning.

---

## Integración con otros namespaces

- **`pm:` (PMBOK)** — la Review es el punto de **validación de entregables con el cliente**: alimenta `pm:monitoring` (verificación del alcance entregado vs comprometido, actualización del estado del producto) y, en el cierre de fase o proyecto, `pm:closing` (aceptación formal del Increment por el sponsor). El feedback re-prioriza el alcance igual que un cambio aprobado en el control de cambios de PMBOK.
- **`pps:` / `lean:` (mejora continua del valor)** — al inspeccionar el producto con quien lo usa, la Review es el mecanismo que mantiene el flujo orientado a **valor para el cliente** (estilo Lean): el feedback expone desperdicio (features sin valor) y demanda real, evitando construir lo que nadie pidió.
- **`pdca:` (PDCA)** — la Review es el **Check** sobre el producto: se contrasta el Increment (resultado del Do del Sprint) contra lo esperado por los stakeholders; el ajuste del Product Backlog es el **Act** que corrige el rumbo del producto. (La Retrospective hace el Check/Act sobre el *proceso*; la Review, sobre el *producto*.)
- **Ciclo THYROX** — la Review vive en **Stage 9 PILOT/VALIDATE** (se valida el Increment con stakeholders reales antes de darlo por bueno) y en **Stage 11 TRACK-EVALUATE** (se evalúa el resultado contra el Sprint Goal y se mide el avance del producto). Su output —backlog actualizado— realimenta el Stage 6 SCOPE del próximo ciclo.

---

## Anti-patrones

- **Mostrar trabajo no-Done como terminado** — exhibir un item "casi listo" como Done falsea el estado del producto y traslada deuda silenciosa al próximo Sprint.
- **Demo unilateral sin diálogo** — si la Review es una presentación donde los stakeholders solo miran, no hubo inspección; el output es el feedback, no el aplauso.
- **Feedback que se pierde en un acta** — recoger comentarios y no convertirlos en items del Product Backlog equivale a no haberlos recogido; el aprendizaje se evapora.
- **Sin stakeholders reales** — una Review donde solo está el equipo es teatro: nadie con poder de decisión sobre el producto inspecciona ni prioriza.
- **Convertir la Review en retrospectiva** — discutir cómo trabajó el equipo en vez de qué se construyó mezcla dos inspecciones distintas; el proceso se inspecciona en `scrum:retrospective`.
- **Cerrar sin re-priorizar el backlog** — si el Product Backlog sale igual que entró, el feedback no tuvo efecto y el próximo Sprint Planning parte de información vieja.

---

## Artefacto esperado

- **Increment demostrado** — registro de qué items Done se mostraron y cuáles no llegaron (con motivo).
- **Feedback capturado** — lista de comentarios de stakeholders ya traducidos a items/cambios de backlog, con origen y motivación.
- **Product Backlog actualizado** — backlog re-priorizado, listo para alimentar el próximo `scrum:sprint-planning`.

---

## Siguiente paso

- Review completa → `scrum:retrospective` (inspección del proceso/equipo) antes de cerrar el Sprint.
- Backlog actualizado → `scrum:sprint-planning` del próximo Sprint, que consume el backlog re-priorizado.
- Increment aceptado formalmente por el sponsor → insumo de `pm:closing` si cierra una fase o entregable.
