---
name: Help
description: Cómo trabajar con THYROX en kaupamex — fases, comandos y dónde vive el estado. No invoca agentes; responde directamente, adaptado al estado actual (lee el SMD para situar).
---

# /thyrox:help — Cómo usar THYROX en kaupamex

No invoques agentes. Responde directamente con lo siguiente, situando al
usuario con el SMD (`docs/source/gestion/pm/siguiente-mejor-decision.rst`).

## Qué es

THYROX es una metodología de gestión empaquetada como skill de Claude Code.
Hablas en lenguaje natural y Claude dirige el ciclo de vida en fases, dejando
todo como **RST + commits en git**. En kaupamex el estado **NO** vive en
`.thyrox/` (decisión bloqueada en `CLAUDE.md`): vive en el submódulo `docs/`
bajo `source/gestion/pm/`.

## Dónde vive el estado (no ROADMAP.md)

| Qué | Dónde |
|---|---|
| Qué sigue (prioridad) | `gestion/pm/siguiente-mejor-decision.rst` (SMD) |
| Work package activo | `gestion/pm/<submodulo>/iniciativas/<slug>/` |
| Definition of Done | `quality/definition-of-done.rst` |
| Lecciones / fallos | `gestion/pm/<submodulo>/lecciones-aprendidas/` |
| Decisiones | `backend/adr/` · `frontend/adr/` · `gestion/decisiones/` |

## Fases → comando → mecanismo

| Quieres… | Comando | Mecanismo |
|---|---|---|
| descubrir / medir / diagnosticar | `/thyrox:discover` · `:measure` · `:analyze` | skills `workflow-*` |
| restricciones / estrategia / scope | `/thyrox:constraints` · `:strategy` · `:plan` | skills `workflow-*` |
| estructurar spec / descomponer | `/thyrox:structure` · `:decompose` | skills `workflow-*` |
| implementar | `/thyrox:execute` | skill `workflow-implement` |
| **aceptar el incremento (gate)** | **`/thyrox:accept`** | agente `increment-acceptor` vs DoD |
| seguimiento / estandarizar | `/thyrox:track` · `:standardize` | skills `workflow-*` |
| **retrospectiva / cierre** | **`/thyrox:retro`** | agente `retro-facilitator` → lecciones |
| auditar coherencia del WP | `/thyrox:audit` | skill `workflow-audit` |
| **estado rápido** | **`/thyrox:status`** | lee SMD + git (sin agente) |

## Lo que lo hace fiable

- El **SMD** es la fuente única de "qué sigue"; **git** es la única
  persistencia (cero backups — I-002).
- Las **reglas globales** (`.claude/rules/`) cargan en cada sesión:
  commit Tim Pope, timestamps ISO 8601, `react-verification-gate`,
  `gitlink-bump-gate`, `principio-rector-rup-arquitectura`, DoD.
- Cada commit en un submódulo se cierra con el **bump del gitlink** del
  superproyecto (`gitlink-bump-gate.md`).
