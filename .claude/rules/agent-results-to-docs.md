# Agent results to docs — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/agent-results-to-docs.md` — se carga en sesiones con
`docs` en scope. Aquí solo el invariante operativo (Opción B, iniciativa
`consolidar-reglas-fuente-unica`, DEC-01/02):

Hook SubagentStop (save-agent-result.mjs) apenda el reporte final de cada subagente al log local append-only.
