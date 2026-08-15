#!/bin/bash
# set-session-phase.sh — no-op en kaupamex (H-API-625).
#
# Wireado como hook UserPromptSubmit en los 13 skills workflow-*/SKILL.md —
# se dispara en cada sesión. El mecanismo original (now.md::phase in-place)
# no tiene equivalente aquí: .claude/CLAUDE.md declara explícitamente que
# "los state files de sesion no se persisten en el filesystem (no hay
# .thyrox/context/) ... no archivos now-*.md". Antes de este fix, la
# ausencia de .thyrox/context/now.md hacía que el script saliera con
# "Error: .thyrox/context/now.md not found" y exit 1 en cada invocación.
#
# Se conserva el hook cableado (retirarlo exige editar 13 frontmatters,
# fuera de alcance de este fix puntual) pero convertido en no-op seguro,
# mismo patrón que el resto de hooks del repo: nunca rompe el flujo.
exit 0
