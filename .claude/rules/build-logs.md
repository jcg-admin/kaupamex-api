# Build logs — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/build-logs.md` — se carga en sesiones con
`docs` en scope. Aquí solo el invariante operativo (Opción B, iniciativa
`consolidar-reglas-fuente-unica`, DEC-01/02):

Logs de build a docs/build-logs/<slug>/ (fuera de source/, git-ignored), naming ISO 8601; nunca /tmp ni stdout efímero.
