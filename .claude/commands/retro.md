---
name: Retro
description: Retrospectiva de cierre de ciclo (THYROX, cierre de Fase TRACK). Conduce la retro (Start/Stop/Continue por defecto), aplica causa raíz, registra episodios de fallo y lecciones, prioriza acciones con dueño y promueve decisiones a ADR. Persiste en lecciones-aprendidas/. Delega en el agente retro-facilitator.
argument-hint: "[formato opcional: start-stop-continue | 4ls | sailboat]"
---

# /thyrox:retro — Retrospectiva (cierre de ciclo)

Captura aprendizajes al cerrar una iniciativa o sprint.

Delega en el subagente **`retro-facilitator`** vía la herramienta Agent. Usa
el formato indicado en `$ARGUMENTS` (default: Start/Stop/Continue).

El agente debe:

1. Conducir la retro y aplicar análisis de causa raíz (5 Whys / Ishikawa).
2. Registrar los fallos del gate como episodios según
   `.claude/rules/memoria-episodica-fallos.md` (frontmatter `:categoria:` +
   `:condicion:` fija; verificar aterrizaje con el grep de retrieval).
3. Priorizar acciones de mejora (impacto/esfuerzo) con dueño y seguimiento.
4. Promover a ADR (`backend/adr/` o `frontend/adr/`) las decisiones que deban
   quedar fijas; escribir
   `docs/source/gestion/pm/<submodulo>/lecciones-aprendidas/<slug>-<fecha>.rst`.

**Salida:** lección persistida (verificada con `git ls-files`) + episodios +
acciones priorizadas + ADRs propuestos. NO usa `.thyrox/`: persiste en el
submódulo `docs/`.
