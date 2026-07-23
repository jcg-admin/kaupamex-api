# CLAUDE.md — api (cheat-sheet local)

Submódulo `api` del monorepo PracticaYoruba (repo GitHub `jcg-admin/kaupamex-api`).
Backend Django 6 + DRF, gestionado con `uv`, tests con pytest contra MariaDB.
El producto se llama **PracticaYoruba** dentro del código (schemas
`practicayoruba_db` / `practicayoruba_qa`; usuario `django_user`).

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
- mysqlclient `2.2.1`, python-decouple `3.8`, Pillow `>=10.3.0`,
  mercadopago `>=2.2.0`, django-cors-headers `4.9.0`
- Test group: pytest `7.4.4`, pytest-django `4.7.0`, factory-boy `3.3.0`
- uv: `package = false` (app Django, no wheel)

## Comandos (todos verificados)

```bash
# Levantar MariaDB (idempotente, socket Unix) — script del submódulo db
bash /home/user/kaupamex-db/scripts/start_db.sh        # o: make db-up

# Gate de conexión (ver .claude/rules/db-conexion-socket.md): debe imprimir un .sock
PYTHONPATH=practicayoruba DJANGO_SETTINGS_MODULE=config.settings.testing \
  python -c "from django.db import connection; \
    print('unix_socket:', connection.settings_dict.get('OPTIONS',{}).get('unix_socket','<NONE>'))"

# Pytest — settings=config.settings.testing, schema practicayoruba_qa (pytest.ini)
# --reuse-db ya está en addopts. NUNCA SQLite (proyecto canónico = MariaDB).
# OJO: la DB es compartida; no recrees el schema con otros agentes corriendo.
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

- **DB por socket Unix** `/run/mysqld/mysqld.sock` (convención del proyecto,
  `config/settings/base.py:77-89`). Si `DB_SOCKET`/`DB_QA_SOCKET` está seteada,
  mysqlclient ignora HOST/PORT.
- **Socket stale**: el contenedor puede caerse → si el gate da `<NONE>` o falla
  la conexión, re-correr `start_db.sh` (idempotente). El script pasa
  `--tmpdir=/tmp` porque `TMPDIR=/tmp/claude-0` no es escribible por `mysql`.
- **`--reuse-db` vs `--create-db`** (pytest.ini:30-34): testing.py declara
  `TEST.NAME=practicayoruba_qa`, así que sin `--reuse-db` Django intenta
  DROP+CREATE en cada run y se cuelga (falta GRANT DROP/CREATE global a
  `django_user`). Reusar la DB; forzar recreación solo con `--create-db`.
- **Migración nueva en QA**: aplicarla con
  `DJANGO_SETTINGS_MODULE=config.settings.testing python manage.py migrate`
  (docs/operaciones.md); pytest aplica migraciones nuevas con `--reuse-db`.
- **Canon error key = `codigo_error`** (no `error_code`); ~198 usos en
  `practicayoruba/apps/`. El gate canon-idioma lo vigila.
- **Zero lazy imports**: imports al top del módulo; el pre-commit lo bloquea.

### Vistas DRF — invariante de seguridad (detalle en el skill `backend-drf`)

- **Autorización por CAPACIDAD, nunca `IsAuthenticated` a secas.** Toda vista
  que exponga datos/acciones va gateada por `HasCapability` (fail-closed: sin
  capacidad declarada → 403). NO usar `permission_classes = [IsAuthenticated]`
  solo — **salta** el modelo de capacidades DEC-11.
- El **detalle de convenciones de vista** (estilo FBV / ViewSet+router / CBV,
  azúcar de capacidad, `drf-spectacular`, gotcha del `.as_view()` manual con
  `@action`, seed de capacidades) vive en el skill on-demand **`backend-drf`**
  (`.claude/skills/backend-drf/SKILL.md`) — invocarlo al implementar/modificar
  endpoints en `src/addons/**`. No se duplica aquí para no engordar el CLAUDE.

## Estructura

```
practicayoruba/apps/            apps Django (cart, catalogue, inventory, ...)
practicayoruba/config/settings/ base.py · development.py · production.py · testing.py
tests/integration/              flujos end-to-end (auth, cart, payments, ...)
tests/{unit,factories,fixtures} unit, factory-boy, fixtures
scripts/                        check_no_lazy_imports.py · check_silent_oks.py · install-hooks.sh
.githooks/pre-commit            gates lazy + canon + silent-OK sobre .py staged
```
