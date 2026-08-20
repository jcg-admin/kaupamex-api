# CLAUDE.md — api (cheat-sheet local)

Submódulo `api` del monorepo PracticaYoruba (repo GitHub `jcg-admin/kaupamex-api`).
Backend Django 6 + DRF, gestionado con `uv`, tests con pytest contra PostgreSQL.
El operador de plataforma (L0) es **Kaupamex**: las bases son `kaupamex_core`
(prod/dev) y `kaupamex_core_qa` (tests), con el rol `django_user`. **PracticaYoruba**
es el L1 de ejemplo (insignia), no el nombre del producto ni de la base.

Este archivo es **solo un cheat-sheet local** — NO redefine gobernanza.

## Gobernanza

La gobernanza vive en el superproyecto, no aquí:

- **`../kaupamex/.claude/CLAUDE.md`** — identidad, flujo de sesión, glosario.
- **`../kaupamex/.claude/rules/`** — reglas no negociables cargadas en cada
  sesión: commit Tim Pope (`commit-conventions.md`), timestamps ISO 8601
  (`timestamps-iso8601-obligatorios.md`), `react-verification-gate.md`,
  `no-lazy-imports.md`, `test-execution-protocol.md`, etc.
- **`.claude/rules/db-conexion-socket.md`** (local) — gate ejecutable de la
  conexión a DB por socket vs TCP.
- **`.claude/rules/commit-conventions.md`** (local) — estilo Tim Pope +
  autor obligatorio (`Nestor Monroy`). Sin Conventional Commits.
- **`.claude/rules/git-workflow.md`** (local) — flujo de ramas: siempre
  `feature/…` → PR → `develop`. Nunca push directo a `develop`/`main`.

## Stack (verificado en `pyproject.toml`)

- Python `>=3.12,<3.15`
- Django `6.0.5`, djangorestframework `3.16.1`,
  djangorestframework-simplejwt `5.5.1`, drf-spectacular `0.29.0`
- psycopg[binary] `>=3.2`, python-decouple `3.8`, Pillow `>=10.3.0`,
  mercadopago `>=2.2.0`, django-cors-headers `4.9.0`
- Test group: pytest `7.4.4`, pytest-django `4.7.0`, factory-boy `3.3.0`
- uv: `package = false` (app Django, no wheel)

## Comandos (todos verificados)

```bash
# PostgreSQL: Debian opera por cluster, no por proceso suelto
pg_isready                                             # ¿responde?
sudo pg_ctlcluster 16 main start                       # si no

# Gate de conexión (ver .claude/rules/db-conexion-socket.md): HOST debe ser el
# directorio del socket — en libpq el socket ES el host, no una opción aparte
DJANGO_SETTINGS_MODULE=config.settings.testing uv run python -c \
  "from django.db import connection as c; \
   print('HOST:', c.settings_dict['HOST'], '| PORT:', c.settings_dict['PORT'])"

# Pytest — settings=config.settings.testing, base kaupamex_core_qa (pytest.ini)
# --reuse-db ya está en addopts. NUNCA SQLite (proyecto canónico = PostgreSQL).
# OJO: la base es compartida; no la recrees con otros agentes corriendo.
uv run pytest --reuse-db -q                              # o: make ci-test
uv run pytest tests/integration/cart/ -q --reuse-db      # subset (make ci-test-fast)

# Checkers de calidad (Makefile / .githooks/pre-commit)
python3 scripts/check_no_lazy_imports.py                 # make check-lazy[-ci]
python3 scripts/check_silent_oks.py                      # make check-silent[-ci]
make check-canon                                         # canon-idioma (cross-submodule)

# Hooks: pre-commit local valida lazy + canon + silent-OKs sobre .py staged
bash scripts/install-hooks.sh                            # make install-hooks
```

Targets de Makefile: `help check-lazy[-ci] check-canon[-ci] test test-coverage
install-hooks db-up ci-test ci-test-fast` (`make help`).

## Convenciones locales / gotchas

- **DB por socket Unix** — en libpq el socket **es el HOST**: un `HOST` que
  empieza con `/` designa el *directorio* del socket (`/var/run/postgresql`) y
  el `PORT` nombra el archivo (`.s.PGSQL.5432`). Por eso los settings resuelven
  `'HOST': _DB_SOCKET or config('DB_HOST')` — no hay opción `unix_socket`.
- **`Peer authentication failed`** no es un problema de credenciales: el
  `pg_hba.conf` de Debian asigna `peer` al canal local. El rol de aplicación
  necesita una regla explícita **por encima** de la genérica; la instala
  `db: provisioners/postgresql/db_setup.sh` (H-DB-05).
- **`--reuse-db` vs `--create-db`** (pytest.ini): testing.py declara
  `TEST.NAME=kaupamex_core_qa`, así que sin `--reuse-db` Django intenta DROP+CREATE
  en cada run. Reusar la base; forzar recreación solo con `--create-db`.
- **Base ≠ schema**: lo que MariaDB llamaba *schema* aquí es una **base**; un
  *schema* es un namespace dentro de ella (`public`). Ver
  `db: .claude/skills/db-postgres/SKILL.md`.
- **Migración nueva en QA**: aplicarla con
  `DJANGO_SETTINGS_MODULE=config.settings.testing python manage.py migrate`
  (docs/operaciones.md); pytest aplica migraciones nuevas con `--reuse-db`.
- **Canon error key = `codigo_error`** (no `error_code`). El gate canon-idioma
  lo vigila.
- **Zero lazy imports**: imports al top del módulo; el pre-commit lo bloquea.

### Vistas DRF — invariante de seguridad (detalle en el skill `backend-drf`)

- **Autorización por CAPACIDAD, nunca `IsAuthenticated` a secas.** Toda vista
  que exponga datos/acciones va gateada por `HasCapability` (fail-closed: sin
  capacidad declarada → 403). NO usar `permission_classes = [IsAuthenticated]`
  solo — **salta** el modelo de capacidades DEC-11.
- El **detalle de convenciones de vista** (estilo FBV / ViewSet+router / CBV,
  azúcar de capacidad, `drf-spectacular`, gotcha del `.as_view()` manual con
  `@action`, seed de capacidades) vive en el skill on-demand **`backend-drf`**
  (`.claude/skills/backend-drf/SKILL.md`); el contrato OpenAPI en
  **`backend-drf-spectacular`**. No se duplica aquí para no engordar el CLAUDE.
- **La invocación de esos skills es un GATE mecánico, no prosa.** Un hook
  `PreToolUse` (`.claude/hooks/inject_drf_skill_gate.py`, ver
  `.claude/rules/drf-skill-gate.md`) dispara en CADA `Edit`/`Write`/`MultiEdit`
  sobre Python del monolito modular (`src/**/*.py` y `tests/**/*.py`) e inyecta
  el recordatorio de invocar `backend-drf` (+ `backend-drf-spectacular` si toca
  la capa DRF) ANTES de escribir. No depende de la memoria del agente.

## Estructura

```
addons/                         los 90 addons de comunidad (sale, stock, account, ...)
src/addons/                     base — el addon del que depende el arranque
src/config/settings/            base.py · development.py · production.py · testing.py
kaupamex-bin                    punto de entrada del producto (≙ odoo-bin)
tests/integration/              flujos end-to-end (auth, cart, payments, ...)
tests/{unit,factories,fixtures} unit, factory-boy, fixtures
scripts/                        check_no_lazy_imports.py · check_silent_oks.py · install-hooks.sh
.githooks/pre-commit            gates lazy + canon + silent-OK sobre .py staged
```
