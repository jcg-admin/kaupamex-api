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

**El reparto por proceso está ADOPTADO — `-n 4` en local, NUNCA en CI**
(directiva del ejecutor 2026-08-27). `pytest-xdist==3.6.1` vive en el grupo
`test` de `pyproject.toml`. Medido pareado, misma población (792 passed):
serie caliente **130.81 s**, `-n 4` caliente **51.50 s** (**2.54×**), `-n 4` en
frío **286.63 s** (**0.46×** — más lento). Por eso:

| Caso | Modo |
|---|---|
| CI (`--create-db`, siempre frío) | **serie** — `-n` ahí empeora |
| local, varios directorios, bases calientes | **`-n 4`** |
| un test o un solo archivo | **serie** |

No va en `addopts`: lo heredarían los tres casos y en dos resta. La base por
worker la resuelve `pytest-django` sufijando `TEST.NAME` con el `workerid`, así
que `kaupamex_core_qa` nunca se toca. Costo de arranque 235 s, equilibrio en la
tercera ejecución. Ver H-API-804.

Los gates estáticos (`check_no_lazy_imports`, `check_silent_oks`,
`check-canon`) cuestan segundos y **sí** se corren siempre. La DB por socket
sigue siendo precondición de cualquier pytest (`pg_isready`; si no responde,
`pg_ctlcluster 16 main start`) y **nunca SQLite**. Un fallo pre-existente se
cita, no se silencia.

Baseline vigente de api: **5 274 passed, 21 skipped, 0 failed** contra
PostgreSQL 16.13 (medido 2026-08-28T00:09:41, cierre del porte de
``ResPartner``, ``api@07ccc097``; 265.97 s con ``-n 4`` y bases calientes).

Sube de **5 182** (medida anterior, ``api@53e6c368``, en serie y 865.38 s).
Los cuatro bloques que cierran ``res_partner.py`` aportan **60** casos —14
restricciones y onchange, 17 vendedor/usuario principal/idioma, 23 alta desde
texto libre y borrado, 6 acciones de vista—; los **32** restantes aterrizaron
entre ambas medidas y **no se desglosan aquí porque no se midieron commit a
commit**. Lo que sí es medida: 0 failed y la cifra sube.

*Métrica:* ``uv run pytest -n 4 -q --reuse-db`` sobre las cuatro bases de
worker ya calientes.
*Ciega a:* la diferencia entre las dos ejecuciones no es sólo de población —la
anterior corrió en serie—, así que el **3.25×** de reloj no es comparable con
el 2.54× pareado de H-API-804: aquél midió la misma población en los dos
modos y éste no.

El build de docs es **opcional**, no parte del DoD.

Motor: PostgreSQL desde `docs: source/backend/adr/adr-028-postgresql.rst`. El
gate de conexión vive en `db-conexion-socket.md` (en libpq el socket **es** el
HOST).
