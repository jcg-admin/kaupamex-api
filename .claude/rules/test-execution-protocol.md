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
script fuera del camino de la suite.

**El subconjunto se DERIVA, no se elige de memoria** (directiva del ejecutor
2026-08-27). Es el módulo tocado **más sus consumidores medidos**, y el
comando va citado junto al resultado:

```bash
grep -rl '<Simbolo>\|<modulo>' --include=*.py tests/ \
    | sed 's|/[^/]*$||' | sort | uniq -c
```

Medido sobre `ir_cron`: los cuatro directorios que salen dan **726 passed,
17 skipped en 101 s** contra **4759 passed en 675 s** de la suite entera —
**6.7×**, y el derivado incluía `tests/integration/mail`, que el elegido a
ojo se saltaba. Más rápido **y** más completo sobre lo que el cambio toca.

**`addons/base` YA NO es disparador automático de la suite entera** — era
demasiado grueso: `base` tiene decenas de archivos y `ir_cron.py` no es
transversal. Lo siguen siendo el **ORM espejado** (`src/orm/`, `src/fields.py`,
`src/models.py`) y **`config/settings`**.

La suite completa queda para tres casos: esos dos mecanismos, **antes de abrir
un PR o al cerrar un bloque** (ahí sí importa la ceguera del derivado — un
consumidor que llega por herencia sin nombrar el símbolo), y cuando el ejecutor
la pide.

Los gates estáticos (`check_no_lazy_imports`, `check_silent_oks`,
`check-canon`) cuestan segundos y **sí** se corren siempre. La DB por socket
sigue siendo precondición de cualquier pytest (`pg_isready`; si no responde,
`pg_ctlcluster 16 main start`) y **nunca SQLite**. Un fallo pre-existente se
cita, no se silencia.

Baseline vigente de api: **4 759 passed, 21 skipped, 0 failed** contra
PostgreSQL 16.13 (medido 2026-08-27T00:48). La cifra anterior de esta línea
—2 235, del 2026-08-06— llevaba tres semanas describiendo un árbol que ya no
existe. El build de docs es **opcional**, no parte del
DoD.

Motor: PostgreSQL desde `docs: source/backend/adr/adr-028-postgresql.rst`. El
gate de conexión vive en `db-conexion-socket.md` (en libpq el socket **es** el
HOST).
