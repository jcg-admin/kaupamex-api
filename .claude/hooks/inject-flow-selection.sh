#!/usr/bin/env bash
# SessionStart hook — inyecta un recordatorio de SELECCIÓN DE FLOW metodológico
# de THYROX al inicio de cada sesión, incluyendo los namespaces ágiles
# scrum-* y kanban-*, para que se consideren de forma automática y no queden
# como skills muertos. Emite JSON con hookSpecificOutput.additionalContext.
# Nunca rompe el flujo: sale 0 siempre.
cat <<'JSON'
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"THYROX — selección de flow metodológico: al abrir un work package, elegir el marco según la tabla 'Selección por necesidad' en .claude/skills/thyrox/SKILL.md (no operar sin flow cuando el trabajo lo amerita). Opciones ágiles disponibles además de pm:/rup:/etc.: scrum-* (desarrollo iterativo en Sprints — backlog-refinement, sprint-planning, daily-standup, sprint-review, retrospective, definition-of-done) y kanban-* (flujo continuo/mantenimiento, pull+WIP — board-setup, wip-limits, flow-metrics, queue-management). Criterio: alcance evolutivo con cadencia → scrum-*; trabajo de llegada continua (bugs/soporte) → kanban-*. Guía: docs/source/gestion/pm/guias/metodologias-agiles.rst."}}
JSON
exit 0
