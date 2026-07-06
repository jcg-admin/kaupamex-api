# Coherence audit gate — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/coherence-audit-gate.md` — se carga en sesiones con
`docs` en scope. Aquí solo el invariante operativo (Opción B, iniciativa
`consolidar-reglas-fuente-unica`, DEC-01/02):

Hook SessionStart inyecta score de coherencia (thyrox-audit.sh --fast); surfacing no bloqueante.
