# Long-running commands — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/long-running-commands.md` — se carga en sesiones con
`docs` en scope. Aquí solo el invariante operativo (Opción B, iniciativa
`consolidar-reglas-fuente-unica`, DEC-01/02):

Comandos >5 min en background (nohup & disown / Monitor con tail -f --pid); nunca foreground >5 min ni sleep largo (dispara SSE timeout).
