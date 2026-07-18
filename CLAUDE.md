# CLAUDE.md — api (cheat-sheet local)

Submódulo `api` del monorepo PracticaYoruba (repo GitHub `jcg-admin/e-commerce-api`).
Backend Django 6 + DRF, gestionado con `uv`, tests con pytest contra MariaDB.
El producto se llama **PracticaYoruba** dentro del código (schemas
`practicayoruba_db` / `practicayoruba_qa`; usuario `django_user`).

Este archivo es **solo un cheat-sheet local** — NO redefine gobernanza.

## Gobernanza

La gobernanza vive en el superproyecto, no aquí:

- **`../e-commerce/.claude/CLAUDE.md`** — identidad, flujo de sesión, glosario.
- **`../e-commerce/.claude/rules/`** — reglas no negociables cargadas en cada
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
bash /home/user/e-commerce-db/scripts/start_db.sh        # o: make db-up

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

### Convenciones de vistas DRF — OBLIGATORIO (no olvidar)

- **Autorización por CAPACIDAD, nunca `IsAuthenticated` a secas.** Toda vista
  que exponga datos/acciones va gateada por `HasCapability` (fail-closed:
  sin capacidad declarada → 403). NO usar `permission_classes =
  [IsAuthenticated]` solo — eso **salta** el modelo de capacidades DEC-11.
  Usar la azúcar declarativa de `addons.authz.permissions`:
  - **Vista de acción única** → **FBV** (ver punto siguiente):
    `@api_view([...])` + `@require_capability('dominio.verbo')`.
  - **ViewSet/ModelViewSet** (CRUD): `permission_classes = [IsAuthenticated,
    HasCapability]` + `permission_map = {'list': 'x.view', 'create': 'x.create'}`.
  - CBV `APIView` (legacy o multi-método complejo): `class V(
    CapabilityRequiredMixin, APIView): required_capability = 'dominio.verbo'`.
  - **Cuenta propia** (el usuario gestiona SU cuenta): capacidad `account.*`
    sembrada en TODOS los roles en `seed_authz` (`self_account_codes` +
    `NAMED_ACTIONS`). Un `required_capability` nuevo DEBE añadirse al catálogo
    de `seed_authz` o el sweep de `test_capability_sugar.py`
    (`unknown_capability_codes`, barre todo el URLconf) falla.
- **Convención de estilo de vista (decisión ejecutor 2026-07-18) — 3 casos:**

  | Estilo | Cuándo | Wiring |
  |---|---|---|
  | **FBV** `@api_view` + `@require_capability` | **acción única** (1 verbo: login, 2FA, cambiar pass) | `path()` → función |
  | **`ViewSet`/`ModelViewSet`** + `permission_map` | **recurso CRUD** (list/retrieve/create/update/destroy + `@action`) | **router** (`DefaultRouter().register`) |
  | **CBV `APIView`** + `CapabilityRequiredMixin` | legacy / multi-método que no es recurso CRUD | `path(..., V.as_view())` |

  Criterio: un endpoint de un solo verbo se implementa function-based (evita el
  boilerplate de una clase por método); un recurso con operaciones CRUD usa
  `ViewSet`. Orden de decoradores en FBV (`@extend_schema` arriba, `@api_view`,
  `@require_capability` **debajo** — más interno, para que DRF lea
  `permission_classes` al envolver)::

      @extend_schema(tags=[...], summary='...', request=Ser|None, responses={...})
      @api_view(['POST'])
      @require_capability('dominio.verbo')
      def mi_accion(request): ...

  - **ViewSet SIEMPRE con router; NUNCA `.as_view({'get':'list'})` manual con
    `@action`** — el bind manual salta el router e **ignora las
    `permission_classes` de la acción** (hueco de seguridad, advertencia DRF).
    Verificado limpio 2026-07-18: **43** `router.register`, **0** `.as_view({…})`
    manual. Gate por acción: `permission_map={action: cap}` o
    `@action(..., permission_classes=[IsAuthenticated, RequireCapability(cap)])`.
    Router prefix **sin** slash final.
  - No hay clase base de proyecto (no existe `BaseAPIView`); lo transversal vive
    en las permission classes + `codigo_error` + drf-spectacular.
  - **`authz_totp` ya está migrado a FBV**; los self-account CBV heredados
    (`ProfileView`, `ChangePasswordView`, `DeactivateAccountView`,
    `LogoutAllSessionsView`) migran en la iniciativa `migrar-self-account-a-fbv`
    (ojo: `ChangePasswordView` usa `ScopedRateThrottle` con `throttle_scope` de
    clase → requiere throttle propio en FBV; `ProfileView` GET+PATCH →
    `@extend_schema(methods=[...])` apilados).
- **drf-spectacular en CADA endpoint nuevo — no olvidar.** Anotar cada handler
  con `@extend_schema(tags=[...], summary='...', request=<Serializer|None>,
  responses={200: OpenApiResponse(description=...), 4xx: ...})`. La API publica
  su OpenAPI con `drf-spectacular`; un endpoint sin `@extend_schema` degrada el
  schema. En FBV multi-método usar `@extend_schema(methods=['GET'], ...)`
  apilados. Import: `from drf_spectacular.utils import extend_schema, OpenApiResponse`.

## Estructura

```
practicayoruba/apps/            apps Django (cart, catalogue, inventory, ...)
practicayoruba/config/settings/ base.py · development.py · production.py · testing.py
tests/integration/              flujos end-to-end (auth, cart, payments, ...)
tests/{unit,factories,fixtures} unit, factory-boy, fixtures
scripts/                        check_no_lazy_imports.py · check_silent_oks.py · install-hooks.sh
.githooks/pre-commit            gates lazy + canon + silent-OK sobre .py staged
```
