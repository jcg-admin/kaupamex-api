# Contenedor corre db+api tests — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/contenedor-corre-db-api-tests.md` — se carga en sesiones con
`docs` en scope. Aquí solo el invariante operativo (Opción B, iniciativa
`consolidar-reglas-fuente-unica`, DEC-01/02):

El contenedor SÍ corre db+api por socket (start_db.sh + uv run pytest --reuse-db); intentar antes de negar la capacidad.
