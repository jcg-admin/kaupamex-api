# Protocolo de ejecución de pruebas — cheat-sheet (canónico en docs)

Regla completa: `docs/.claude/rules/test-execution-protocol.md` — se carga en
sesiones con `docs` en scope. Procedimiento humano:
`docs: source/normativa/procedimientos/proc-ejecutar-pruebas.rst`.

Aquí solo el invariante operativo (Opción B, iniciativa
`consolidar-reglas-fuente-unica`, DEC-01/02):

**La suite completa NO se corre por defecto** (directiva del ejecutor
2026-08-06, reiterada). Se corre **el subconjunto que el cambio toca**: el
addon tocado (`uv run pytest tests/unit/<x>/ tests/integration/<x>/ -q
--reuse-db`), nada de pytest si el cambio es sólo `.rst`/`.claude/**` o un
script fuera del camino de la suite, y la pila entera **sólo** cuando se toca
un mecanismo transversal (ORM espejado, `config/settings`, `addons/base`) o
cuando el ejecutor la pide.

Los gates estáticos (`check_no_lazy_imports`, `check_silent_oks`,
`check-canon`) cuestan segundos y **sí** se corren siempre. La DB por socket
sigue siendo precondición de cualquier pytest (`pg_isready`; si no responde,
`pg_ctlcluster 16 main start`) y **nunca SQLite**. Un fallo pre-existente se
cita, no se silencia.

Baseline vigente de api: **2 235 passed, 5 skipped, 0 failed** contra
PostgreSQL 16.13 (2026-08-06). El build de docs es **opcional**, no parte del
DoD.

Motor: PostgreSQL desde `docs: source/backend/adr/adr-028-postgresql.rst`. El
gate de conexión vive en `db-conexion-socket.md` (en libpq el socket **es** el
HOST).
