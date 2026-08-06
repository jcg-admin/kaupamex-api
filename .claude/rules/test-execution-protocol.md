# Protocolo de ejecución de pruebas — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/test-execution-protocol.md` — se carga en
sesiones con `docs` en scope. Procedimiento humano:
`docs: source/normativa/procedimientos/proc-ejecutar-pruebas.rst`.

Aquí solo el invariante operativo (Opción B, iniciativa
`consolidar-reglas-fuente-unica`, DEC-01/02):

Antes de declarar una T-NNN cerrada o un commit "sin regresión", correr las
**tres** capas, no solo el módulo tocado: **db** (`pg_isready`; si no responde,
`pg_ctlcluster 16 main start`), **api** (`uv run pytest` completo contra
PostgreSQL real — **nunca SQLite**), **ui** (jest completo, con el gate duro de
Node v22 antes de `npm ci`). Sin las tres verdes —o con los fallos
pre-existentes documentados y citados— no se cierra ni se commitea como verde.

Baseline vigente de api: **2 235 passed, 5 skipped, 0 failed** contra
PostgreSQL 16.13 (2026-08-06). El build de docs es **opcional**, no parte del
DoD.

Motor: PostgreSQL desde `docs: source/backend/adr/adr-028-postgresql.rst`. El
gate de conexión vive en `db-conexion-socket.md` (en libpq el socket **es** el
HOST).
