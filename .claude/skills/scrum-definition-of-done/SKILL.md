---
name: scrum-definition-of-done
description: "Use when defining or maintaining the Definition of Done — the shared quality checklist every increment must meet to be considered finished. scrum:definition-of-done — establish, version, and evolve the DoD aligned with the project's real CI gates (automated tests, OpenAPI, code review, no new technical debt)."
allowed-tools: Read Glob Grep Bash Write Edit
effort: medium
disable-model-invocation: true
metadata:
  triggers: ["Definition of Done", "DoD", "increment done criteria", "quality gate scrum", "done checklist"]
updated_at: 2026-06-02
---

# /scrum-definition-of-done — Scrum: Definition of Done

> *"The Definition of Done is the team's shared agreement on quality. An increment is not 'done' because someone says so — it is 'done' because it satisfies every item of the DoD. Without an explicit DoD, 'done' means whatever each person needs it to mean, and velocity becomes a fiction."*

Define y mantiene la **Definition of Done (DoD)**: el checklist de calidad que TODO incremento debe cumplir para considerarse terminado. La DoD es transversal — aplica a todas las historias y no se negocia por historia individual. Su valor depende de que sea **explícita, compartida y verificable**, y de que ningún item se marque "Done" sin cumplirla por completo.

**THYROX Stage:** Stage 9 PILOT/VALIDATE / Stage 12 STANDARDIZE.

**Outputs clave:** Definition of Done versionada · checklist por incremento.

---

## Pre-condición

Requiere:
- Backlog con historias que produzcan incrementos verificables
- Acceso a los gates reales del proyecto: pipeline de CI, suites de test (api, ui, E2E), generación de OpenAPI, proceso de code review
- Acuerdo del equipo de que la DoD es vinculante (no aspiracional)

---

## Cuándo usar este paso

- Al arrancar un equipo o iniciativa sin una DoD explícita escrita
- Cuando "done" significa cosas distintas para distintas personas y aparecen reaperturas
- Durante la retrospective, cuando un defecto recurrente expone un gap en la DoD
- Al endurecer la DoD tras estabilizar el pipeline (más gates automatizables)

## Cuándo NO usar este paso

- Para criterios de aceptación de UNA historia concreta — esos son acceptance criteria, específicos de la historia, no la DoD transversal
- Para inflar la DoD con items no verificables ("código limpio", "bien documentado") sin un check objetivo detrás

---

## La Definition of Done en e-commerce

La DoD se alinea con los gates **reales** del proyecto PracticaYoruba — no con un ideal abstracto. Cada item debe ser verificable con un comando o evidencia observable.

| # | Item de la DoD | Verificación (PROVEN) |
|---|----------------|------------------------|
| 1 | Tests automatizados api en verde en CI | `cd api && uv run pytest --create-db` exit 0 |
| 2 | Tests automatizados ui en verde | `cd ui && npm test -- --watchAll=false --ci` (Node v20) |
| 3 | Flujos críticos E2E verdes | suite Playwright pasa en CI |
| 4 | Endpoint nuevo/modificado en OpenAPI | drf-spectacular regenera schema sin drift |
| 5 | Code review aprobado | PR aprobado por al menos un revisor distinto del autor |
| 6 | Sin deuda técnica nueva | hallazgos documentados en `audits/hallazgos-<slug>.rst` si los hay; lazy imports = 0 |
| 7 | Documentación de impacto actualizada | UC / FR / ADR tocados según las 8 capas, cuando aplica |
| 8 | Changelog del WP actualizado | entrada en `progreso-<slug>.rst` |

**Regla de oro:** la DoD es un AND lógico. Un incremento con 7 de 8 items cumplidos NO está done — está al 0% de done, porque "casi terminado" no es un estado entregable.

---

## Actividades

| Actividad | Output | Técnica clave |
|-----------|--------|---------------|
| **1. Inventariar gates reales** | Lista de gates ejecutables | Mapear CI + suites + OpenAPI + review |
| **2. Redactar la DoD** | DoD versionada (v1.0.0) | Cada item con su verificación objetiva |
| **3. Socializar y acordar** | DoD firmada por el equipo | Acuerdo explícito, visible en el tablero |
| **4. Aplicar por incremento** | Checklist por incremento | Marcar item por item con evidencia |
| **5. Evolucionar en retrospective** | DoD vNext | Bump semver; registrar el motivo del cambio |

---

## Criterio de completitud — ¿DoD establecida y operativa?

**DoD operativa (todos los siguientes):**
1. La DoD está escrita, versionada y es accesible para todo el equipo
2. Cada item tiene una verificación objetiva (comando, gate de CI, o evidencia)
3. El equipo acordó que la DoD es vinculante para TODA historia
4. Existe un checklist por incremento que se completa item por item antes de marcar "Done"
5. La DoD se revisa en cada retrospective y evoluciona vía bump de versión

**Requiere más iteración:**
- Items de la DoD que nadie sabe cómo verificar — no son DoD, son deseos
- "Done" declarado con la suite roja o con OpenAPI en drift — viola la regla de oro
- La DoD existe en un documento pero nadie la consulta al cerrar historias

---

## Artefacto esperado

`{wp}/standardize/definition-of-done.md` (DoD versionada del equipo)
+ checklist por incremento en el `progreso-<slug>.rst` de la iniciativa.

---

## Red Flags — señales de DoD mal gestionada

- **"Done" sin la DoD completa** — un item marcado terminado con 1+ check de la DoD sin cumplir; la deuda invisible entra exactamente por aquí
- **DoD aspiracional, no verificable** — items como "código de calidad" sin un gate objetivo detrás; no se pueden auditar
- **DoD que no evoluciona** — una DoD idéntica durante 6 meses mientras el pipeline gana gates automatizables indica que la retrospective no la toca
- **DoD por historia** — confundir acceptance criteria (por historia) con DoD (transversal); cada uno tiene su rol
- **DoD que el equipo no conoce** — si al preguntar "¿qué significa done aquí?" hay tres respuestas distintas, la DoD no está compartida
- **Tests verdes parciales declarados como verdes** — declarar la suite verde al 57% mientras corre (ver `test-execution-protocol.md`) corrompe la trazabilidad de la DoD

---

## Integración con otros namespaces

- **`rm-validation`:** la validación de requisitos (sign-off de stakeholders) y la DoD son gates complementarios. `rm-validation` confirma que el incremento responde al requisito correcto; la DoD confirma que está construido con la calidad correcta. Un incremento pasa AMBOS o no está done.
- **Gates de test del proyecto (`test-execution-protocol.md`):** la DoD instancia los tres layers obligatorios (db up, api `uv run pytest --create-db`, ui jest) como items no negociables. La DoD no inventa gates nuevos: hereda los del protocolo de pruebas.
- **`quality` / capa 7 (8 capas):** la DoD es la proyección operativa de los estándares de quality a nivel de incremento. Lo que quality define como TDD y tests-implementados, la DoD lo vuelve un check ejecutable por historia.
- **Ciclo THYROX:** la DoD se valida en Stage 9 PILOT/VALIDATE (¿el incremento piloto cumple la DoD?) y se estandariza en Stage 12 STANDARDIZE (la DoD pasa a ser el estándar del equipo, versionado).

---

## Limitaciones

- La DoD garantiza un piso de calidad uniforme, no la ausencia total de defectos — un increment puede cumplir toda la DoD y aun así tener un bug que ningún gate captura; ese gap alimenta el siguiente item de la DoD vía retrospective
- Una DoD demasiado estricta para gates aún no automatizables introduce fricción manual; la DoD debe crecer al ritmo en que los gates se automatizan, no antes
- La DoD es del equipo, no del individuo — endurecerla sin acuerdo del equipo la convierte en imposición y deja de ser un acuerdo compartido

---

## Siguiente paso

- DoD operativa y aplicada → continuar entregando incrementos con checklist por incremento
- Defecto recurrente detectado → llevar a retrospective, evolucionar la DoD (bump semver) y volver a aplicar
