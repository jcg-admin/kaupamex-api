# Background tasks (bug sweep) — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/bash-background-tasks.md` — se carga en sesiones con
`docs` en scope. Aquí solo el invariante operativo (Opción B, iniciativa
`consolidar-reglas-fuente-unica`, DEC-01/02):

Loop de subagentes: lanzar Agent(bg) y esperar con Monitor sin trabajo intermedio; repos de escritura disjuntos por tanda paralela.
