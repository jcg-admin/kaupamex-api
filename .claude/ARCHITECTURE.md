```yml
created_at: 2026-04-20 13:45:00
updated_at: 2026-08-15 05:52:00
project: kaupamex (api)
author: NestorMonroy
status: Aprobado
```

# ARCHITECTURE.md — Inventario Canónico de Agentes (kaupamex-api)

> **Corregido 2026-08-15.** Esta versión reemplaza un inventario heredado del
> template THYROX genérico que nunca se ajustó a este repo. Medido contra
> `.claude/agents/*.md` real: declaraba **28** agentes, existían **27**, y la
> composición no coincidía en ambas direcciones — 4 filas describían agentes
> que nunca se generaron aquí (`nodejs-expert`, `postgresql-expert` con
> contenido de plantilla, `react-expert`, `webpack-expert`), y **3** agentes
> reales del repo no estaban documentados (`gate-consistency-evaluator`,
> `increment-acceptor`, `retro-facilitator`). Ver la iniciativa que originó
> esta corrección en `docs: gestion/pm/api/iniciativas/` (rama
> `feature/actualizar-agentes-claude-api`).

## Agentes instalados (27)

| Nombre | Función | Tipo | Solapamientos conocidos |
|--------|---------|------|------------------------|
| agentic-reasoning | DEPRECATED — absorbido en deep-dive como Capa 7 (calibración epistémica) | analysis | deep-dive (Capa 7) |
| agentic-validator | Valida código Python agentic contra catálogo AP-01..AP-42 | analysis | — |
| ba-coordinator | Coordinator BABOK — Business Analysis Body of Knowledge (6 knowledge areas) | coordinator | — |
| bpa-coordinator | Coordinator BPA — Business Process Analysis (As-Is → To-Be, 6 fases) | coordinator | — |
| cp-coordinator | Coordinator CP — Consulting Process McKinsey/BCG (Issue Tree, MECE, 7 fases) | coordinator | — |
| deep-dive | Análisis adversarial de artefactos: documentos, código, arquitecturas, decisiones. Capa 7: calibración THYROX automática para artefactos WP | analysis | agentic-reasoning (absorbido) |
| deep-review | Análisis de cobertura entre fases consecutivas del WP; análisis de repos/docs externos | analysis | pattern-harvester (trigger distinto) |
| diagrama-ishikawa | Análisis de causa raíz con diagramas Ishikawa (espina de pescado) | analysis | — |
| dmaic-coordinator | Coordinator DMAIC — Six Sigma (Define/Measure/Analyze/Improve/Control, 5 fases) | coordinator | lean-coordinator (misma estructura DMAIC) |
| gate-consistency-evaluator | Evalúa claims de un artefacto contra decisiones previas y artefactos de stages anteriores. `output_key=consistencia` | gate | increment-acceptor (gate distinto: consistencia vs DoD) |
| increment-acceptor | Juez de aceptación de incrementos (THYROX gate 6→7 / EXECUTE→TRACK) contra la Definition of Done. `output_key=aceptacion` | gate | gate-consistency-evaluator (gate distinto) |
| lean-coordinator | Coordinator Lean Six Sigma — eliminación de desperdicios (5 fases, VSM) | coordinator | dmaic-coordinator (estructura similar) |
| pattern-harvester | Extrae patrones accionables de corpus de deep-dive y calibración; mapea a componentes THYROX | analysis | deep-review (input distinto) |
| pdca-coordinator | Coordinator PDCA — ciclo Plan/Do/Check/Act (4 etapas) | coordinator | — |
| pm-coordinator | Coordinator PMBOK — PMI project management (5 grupos de proceso) | coordinator | — |
| postgresql-expert | Especialista PostgreSQL: schema, migrations Django, índices, extensiones (pg_trgm, unaccent) | expert | — |
| pps-coordinator | Coordinator PPS — Practical Problem Solving Toyota TBP (A3 Report, 6 fases) | coordinator | — |
| retro-facilitator | Facilita la retrospectiva al cerrar una iniciativa/ciclo (THYROX cierre, Fase TRACK). `output_key=retro` | general | — |
| rm-coordinator | Coordinator RM — Requirements Management (elicitation, análisis, spec, validación) | coordinator | ba-coordinator (overlap en análisis de reqs) |
| rup-coordinator | Coordinator RUP — Rational Unified Process (4 fases iterativas, milestones LCO/LCA/IOC/PD) | coordinator | — |
| skill-generator | Genera archivos de skill/agente desde templates del registry para una tecnología | infra | tech-detector (precede a skill-generator) |
| sp-coordinator | Coordinator SP — Strategic Planning (PESTEL/SWOT, BSC, OKRs, 8 fases) | coordinator | — |
| task-executor | Ejecuta tareas atómicas de un task-plan.md (T-NNN checkboxes) | general | task-planner (roles disjuntos: ejecutar vs planificar) |
| task-planner | Descompone trabajo nuevo en tareas T-NNN; nunca ejecuta | general | task-synthesizer (input distinto: fresh vs corpus) |
| task-synthesizer | Consolida outputs de análisis existentes (deep-dive, pattern-harvester) en task-plan | general | task-planner (trigger distinto: corpus vs scratch) |
| tech-detector | Detecta stack tecnológico del proyecto analizando configs, deps y estructura | infra | skill-generator (orquestación secuencial) |
| thyrox-coordinator | Coordinator genérico THYROX — lee YAML dinámicamente, resuelve cualquier metodología registrada | coordinator | Todos los coordinators específicos |

## Tipos de agente

| Tipo | Descripción | Agentes |
|------|-------------|---------|
| coordinator | Orquesta un proceso metodológico con pasos y tollgates formales | ba, bpa, cp, dmaic, lean, pdca, pm, pps, rm, rup, sp, thyrox-coordinator (12) |
| expert | Especialista en tecnología específica del stack real de api | postgresql-expert (1) |
| analysis | Produce análisis de artefactos, corpus o fase-a-fase; salida en markdown | agentic-reasoning, agentic-validator, deep-dive, deep-review, diagrama-ishikawa, pattern-harvester (6) |
| gate | Evalúa un artefacto/incremento contra un contrato formal; retorna veredicto estructurado (`output_key`) | gate-consistency-evaluator, increment-acceptor (2) |
| infra | Infraestructura del sistema: detecta stack, genera skills | skill-generator, tech-detector (2) |
| general | Propósito general de planning/ejecución/cierre del ciclo de trabajo THYROX | task-executor, task-planner, task-synthesizer, retro-facilitator (4) |

## Origen de los archivos — no hay pipeline de generación en este repo

> **Corregido.** La versión anterior de esta sección afirmaba que los 28
> agentes tenían YML en `.thyrox/registry/agents/`, generados por
> `bootstrap.py` (10 de ellos) o instalados como artefacto manual (18).
> Verificado en este turno: **`.thyrox/` no existe** en kaupamex-api (decisión
> documentada en `.claude/CLAUDE.md` — el proyecto no importó ese directorio
> del template), y el único `bootstrap.py` del repo es
> `addons/authz/bootstrap.py`, un módulo de la app Django sin relación con
> generación de agentes.

Los 27 archivos de `.claude/agents/` son **artefactos estáticos**, editados
directamente. No existe un pipeline `tech-detector → skill-generator` que los
regenere en este repo — `skill-generator.md`/`tech-detector.md` documentan un
proceso que el template original preveía, pero que kaupamex-api nunca ejecutó
sobre sí mismo (de haberlo hecho, habría detectado Django+PostgreSQL, no
MySQL/Node.js/React/Webpack — de ahí el drift que esta corrección cierra).

## Detección de agentes zombies

Un agente zombie es un `.md` instalado sin invocación documentada en las
últimas iniciativas y con descripción obsoleta.

**Criterios de zombie:**
1. `.md` instalado en `.claude/agents/`
2. Sin invocación documentada en `progreso-<slug>.rst` recientes ni `git log`
3. Descripción obsoleta o solapada completamente con otro agente

**Zombies actuales:**

| Agente | Estado | Razón |
|--------|--------|-------|
| agentic-reasoning | DEPRECATED — candidato a retiro | Funcionalidad absorbida en deep-dive (Capa 7). Mantener hasta confirmar que deep-dive cubre todos los casos de uso observados. |

**Proceso de cleanup:**
1. Identificar agente zombie
2. Verificar en las iniciativas recientes: ¿fue invocado explícitamente?
3. Si no hay invocación: marcar DEPRECATED en el `.md`
4. En la siguiente pasada de mantenimiento: eliminar si sigue sin uso

## Relaciones de orquestación

```
task-planner  → task-executor             (planificar → ejecutar)
deep-dive     → pattern-harvester         (analizar corpus → extraer patrones)
pattern-harvester → task-synthesizer      (patrones → task-plan consolidado)
thyrox-coordinator ←→ {coordinadores específicos}  (fallback genérico vs. especializado)
increment-acceptor / gate-consistency-evaluator → cierre de Stage/incremento
```

## Referencias

- `.claude/references/agent-spec.md` — spec formal de frontmatter de agentes (verificado, existe).
- `.claude/references/gate-calibrated-contracts.md` — contrato de schema para los agentes tipo `gate`.
- `.claude/skills/thyrox/references/evidence-classification.md` — clasificación PROVEN/INFERRED/SPECULATIVE que consumen gate-consistency-evaluator e increment-acceptor.

> Los enlaces heredados a `adr-coordinators-static-artifacts.md`,
> `adr-python-mcp-manual-skill.md` y `.thyrox/registry/agents/README.md` se
> retiraron: ninguno de los tres existe en este repo (verificado con `find`
> en el mismo turno que esta corrección).
