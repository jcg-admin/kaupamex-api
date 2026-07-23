```yml
type: Convención de Proyecto
category: Ejecución de pruebas db + api + ui
version: 1.0.0
created_at: 2026-05-21 04:33:50
updated_at: 2026-05-21 04:33:50
applies_to: kaupamex v1.0.0+
```

# Protocolo de Ejecución de Pruebas — db + api + ui

> Cargado automáticamente en cada sesión.
> Regla NO NEGOCIABLE antes de declarar tests verdes o cerrar
> una T-NNN.

> **Origen:** sesión 2026-05-21. Falla detectada por el ejecutor:
> el agente corrió solo la suite del archivo modificado (17
> tests de `webhooks` + 5 de `apiService`) y declaró "no
> regresión" sin verificar las suites completas. Resultado: 22
> fallos pre-existentes invisibles + 1 zombie process. Esta
> regla cierra el loop.

## Regla principal

**Antes de declarar una T-NNN cerrada o un commit como "no
regression", correr los TRES layers de la pila completa:**

1. **db** — verificar que MariaDB está up y responde via socket.
2. **api** — `pytest` completo contra MariaDB real (NUNCA SQLite).
3. **ui** — `npx jest` completo.

Sin los 3 verdes (o con fallos pre-existentes documentados
explícitamente), **no se cierra la T-NNN ni se commitea como
"verde"**.

## Arquitectura de conexión (siempre considerar las 3 capas)

```
   ui (jest)                api (pytest)              db (MariaDB)
   ───────                  ────────────              ─────────────
   src/services/            apps/**/views.py          /run/mysqld/
   apiService.js            apps/**/models.py         mysqld.sock
   /api/v1/cart/    HTTP    DRF + simplejwt   socket  practicayoruba_db
                ───────►                  ──────►     practicayoruba_qa
   webpack devServer.proxy  django.db.backends
   localhost:8000           .mysql
```

- **db ↔ api**: socket Unix `/run/mysqld/mysqld.sock` o TCP
  `127.0.0.1:3306`. El proyecto declara socket como canónico
  ("se tienen que conectar x socket"); el config actual usa
  TCP (drift pendiente — ver "Drifts conocidos" abajo).
- **ui ↔ api**: HTTP via fetch a `process.env.API_URL ||
  http://localhost:8000`. Webpack `devServer.proxy` reenvía
  `/api/*` al backend en dev (`webpack.config.js:242-245`).
- **api ↔ db**: `config.settings.{base,testing}` con
  `ENGINE=django.db.backends.mysql`, schemas `practicayoruba_db`
  (prod) y `practicayoruba_qa` (testing). Usuario `django_user`.

## Pre-condición: DB activa

Antes de cualquier `pytest`:

```bash
bash /home/user/kaupamex/db/scripts/start_db.sh
```

Idempotente: si ya está activo, informa y sale. Si no, arranca
`mariadbd` con `--socket=/run/mysqld/mysqld.sock`. Espera hasta
20 s + ejecuta `verify.sh` (debe terminar en `OK: 26`).

**Verificar socket existe:**

```bash
ls -la /run/mysqld/mysqld.sock     # debe existir, owner mysql
mariadb -u django_user -pdjango_pass --socket=/run/mysqld/mysqld.sock -e "SELECT 1"
```

## Comandos canónicos por capa

### Capa db — verificación

```bash
cd /home/user/kaupamex/db
bash scripts/start_db.sh           # arranca + verify
bash scripts/verify.sh             # solo verify
```

### Capa api — suite completa contra MariaDB real

```bash
cd /home/user/kaupamex/api
python -m pytest --tb=no -q        # suite completa (~7 min, 1066+ tests)
python -m pytest tests/integration/payments/ -v  # subset por modulo
python -m pytest -k "test_name_pattern"          # subset por patron
```

**pytest.ini** declara `--reuse-db` (no recrear schema cada
run) y `-p no:randomly` (orden determinista por deadlocks
intermitentes 1213). Settings: `config.settings.testing`,
schema `practicayoruba_qa`.

**NUNCA usar SQLite.** El proyecto declara MariaDB como BD
canónica (FULLTEXT INDEX, JSON columns, sp's). Cualquier
`pytest` que apunte a SQLite es un bug de configuración.

### Capa ui — suite Jest completa

**GATE DURO de versión de Node ANTES de correr jest (L-012).** `.nvmrc` fija
*qué* versión, pero NO carga nvm. En un shell nuevo `nvm` no está cargado →
`nvm use` falla silencioso → `node` cae al del sistema (v18) → `npm ci` rompe
con `EBADENGINE`. Un `EBADENGINE` de node **invalida el gate** (mide la
toolchain equivocada).

```bash
cd /home/user/kaupamex/ui
# 1) cargar nvm explícito (no se auto-carga en shell develop — ver D-07)
export NVM_DIR="$HOME/.nvm"; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm use                             # lee .nvmrc (=20)
# 2) GATE DURO: si no es v20.x, PARAR (no correr npm ci/test)
node -v | grep -q '^v20\.' || { echo "Node != v20; PARAR"; exit 1; }
# 3) instalar exacto del lock (sin EBADENGINE de node)
npm ci --ignore-scripts             # --ignore-scripts evita husky en CI
# 4) suite
npm test -- --watchAll=false --ci   # alias de jest; baseline 779/780 (1 skip)
npx jest --testPathPattern="apiService"   # subset por patrón
```

### Build docs (cuando se tocan RST) — OPCIONAL

```bash
cd /home/user/kaupamex/docs
make html                           # exit 0, 0 warnings nuevos
```

> **Directiva ejecutor 2026-05-29:** el build Sphinx de docs es
> **opcional** — no bloquea el commit ni es parte del DoD obligatorio.
> Correr solo si hay sospecha fundada de error de sintaxis RST
> (nueva directiva, cambio de toctree, etc.) o si el ejecutor
> lo solicita explícitamente.

## Definition of Done — commit en RUP Construction

Antes de marcar una T-NNN como `[x]` y cerrar el commit:

```
[ ] DB está activa (start_db.sh exit 0 + socket vivo).
[ ] api/ — pytest completo corre.
    [ ] Tests del módulo tocado: 100% verde sin regresión.
    [ ] Suite completa: # fallos == baseline previo o documentado
        explicitamente como pre-existente con cita git log.
[ ] ui/ — jest completo corre.
    [ ] Tests del módulo tocado: 100% verde sin regresión.
    [ ] Suite completa: idem baseline check.
[ ] docs/ — OPCIONAL: make html solo si hay sospecha de error RST.
[ ] hygiene: ps -eo pid,etime,cmd | grep -E "until|pytest|jest"
    sin zombies míos huérfanos (kill antes de cerrar el turno).
```

**Anti-patrón documentado (origen de esta regla):**

> "Corrí solo la suite del archivo modificado y declaré 'no
> regression'. La suite completa tenía 22 fallos pre-existentes
> que no documenté, propagando deuda invisible".

## Drifts conocidos del entorno

1. **Socket no configurado en Django settings.** `config/settings/
   {base,testing}.py` usan `HOST=127.0.0.1 PORT=3306` (TCP) en
   lugar de `OPTIONS['unix_socket']='/run/mysqld/mysqld.sock'`.
   Performance ~marginal (1 ms diferencia por handshake) pero
   viola la convención declarada del proyecto. Iniciativa
   sucesora pendiente: `migrar-django-db-a-socket-unix`.

2. **~~22 tests pre-existentes con fallos~~ (SUPERADO 2026-06-02).**
   El baseline 2026-05-21 (`--reuse-db`, pre-H-API) listaba 22
   fallas en auth, cart, catalogue, inventory, orders, payments
   msi, product_discounts, reviews, settings_app. **Ya no aplica:**
   tras la iniciativa `migrar-api-a-uv-pyproject` (H-API-01..07),
   el gate canónico `uv run pytest --create-db` da **1479 passed,
   0 failed, 0 errors** a HEAD (WSL, MariaDB 11.8, 2026-06-02).
   La causa de fondo de varias de esas 22 era la 0016 que abortaba
   el migrate from-scratch (H-API-01) — enmascarada por `--reuse-db`.
   Snapshot histórico en `progreso-corregir-hallazgos-buyer-compra-
   end-to-end.rst` (2026-05-21T04:33:50). Ver
   `pm/reportes/inventario-deuda-maestro` (E-02).

## Hygiene de procesos zombies

Antes de cerrar cada turno:

```bash
# Listar procesos largos de mi sesión
ps -eo pid,etime,cmd | grep -E "until|pytest|jest|manage.py" | grep -v grep

# Si hay alguno mío huérfano (e.g. until loop sin --pid), kill
kill <pid>
```

**Anti-patrones específicos:**

- `Bash run_in_background=true` con `until grep ...` sin
  marcador `EXIT=` garantizado en el log → el `until` queda
  esperando para siempre.
- `Monitor` sin `tail -f --pid=$PID` (ver
  `.claude/rules/long-running-commands.md` R-2.1.1).
- `pytest` lanzado en background y luego matado externamente —
  deja shells trackeadas en el agent harness.

## Relación con otras reglas

- **`calibration-verified-numbers.md`**: el conteo de pasa/fail
  debe venir de `pytest -q` real, no inventado.
- **`long-running-commands.md`**: pytest completo (~7 min) cae
  en R-2.1 (5-30 min). Usar `nohup` + `Monitor tail -f --pid`.
- **`build-logs.md`**: salida de pytest se guarda en
  `docs/build-logs/<slug>/pytest-<ISO>.log` si va a citarse
  en un artefacto.
- **`auto-audit-before-writing.md`**: la auto-audit pre-Write
  no reemplaza la regression — son ortogonales. Auto-audit
  protege premisa; regression protege funcionalidad.

## Referencia humana (RST)

Procedimiento detallado en español + comandos copy-paste:
`docs/source/normativa/procedimientos/proc-ejecutar-pruebas.rst`.
