```yml
type: Reference (lazy-load on-demand)
applies_when: Se escribe/modifica un test de un endpoint DRF (autenticación, payload, assert de respuesta)
created_at: 2026-07-18 03:36:34
status: Aprobado
version: 1.0.0
source: DRF api-guide/testing
```

# DRF Testing — pytest-django + `APIClient`, no las `APITestCase` de DRF

> DRF ofrece helpers de test (`APIClient`, `APIRequestFactory`,
> `force_authenticate`) **y** clases xUnit (`APITestCase`, …). El proyecto usa
> los **helpers** sobre **pytest-django** (funciones + fixtures) — **no** las
> clases `APITestCase`/`unittest`. Todo corre contra **MariaDB real**, nunca
> SQLite (ver `test-execution-protocol.md`).

## Estilo — pytest, no `unittest`

PROVEN 2026-07-18 (`tests/`): **0** `APITestCase` / `APITransactionTestCase` /
`APISimpleTestCase` / `URLPatternsTestCase`, **0** `RequestsClient`. Los tests son
funciones `def test_*` con **fixtures**, no métodos de una `TestCase`. `pytest.ini`
fija `DJANGO_SETTINGS_MODULE=config.settings.testing`, `--reuse-db`,
`-p no:randomly`, `--strict-markers`.

- **`APIClient`** — el vehículo principal: **53** usos. Interfaz igual a la del
  `Client` de Django (`.get/.post/.put/.patch/.delete`).
- **`APIRequestFactory`** — **9** usos, sólo para probar una vista **directo**
  (cuando se necesita el `Request` de DRF o inspeccionar antes del ciclo view).
- **`format='json'`** explícito en los `.post/.put/.patch`: **no** hay
  `TEST_REQUEST_DEFAULT_FORMAT` en settings (PROVEN) → el default de DRF es
  `multipart`; para JSON hay que pedirlo. Pasarlo siempre que el cuerpo sea JSON.

## Fixtures compartidas — `tests/conftest.py`

El proyecto centraliza los clientes en `conftest.py` (PROVEN 2026-07-18). **Reusar
estas fixtures**, no instanciar `APIClient()` a mano salvo que se necesite un
cliente en un estado especial:

| Fixture | Qué es |
|---|---|
| `api_client` | `APIClient()` **sin autenticar**. |
| `auth_client` | `api_client` + `force_login(user)` — usuario comprador, **por sesión**. |
| `admin_client` / `admin_auth_client` | `api_client` + `force_login(admin_user)` — admin, por sesión. |
| `user` / `auth_user` / `admin_user` | usuarios de prueba (`db`). |

Autouse (siempre activas): `clear_rate_limit_cache` (limpia el cache de throttle
entre tests, ver `throttling.md`), `mariadb_keepalive`, `db_objects_setup`
(session-scoped: despliega funciones/vistas/SPs SQL en el schema QA).

## `force_login` (Django) vs `force_authenticate` (DRF) — la distinción clave

El proyecto usa **auth de sesión** (ADR-018, ver `authentication.md`), así que la
elección importa:

- **`force_login(user)`** (Django) — lo que usan las fixtures `auth_client`/
  `admin_client`. **Crea una sesión Django real** (`session_key` poblado). Es el
  camino fiel al runtime: la cookie de sesión es la auth de producción. Preferirlo
  para el caso normal.
- **`client.force_authenticate(user)`** (DRF) — **36** usos. Fija `request.user`
  directo **sin crear sesión** (`session_key=''`). Atajo cuando no se necesita la
  sesión. La doc de DRF avisa que fijar `.user` así "sólo funciona si hay
  SessionAuthentication" — aquí **sí** la hay, por eso funciona.

**Gotcha PROVEN (DEC-12 reauth):** una mutación sensible (`permissions.full`) exige
una sesión reautenticada fresca. Como `force_authenticate` deja `session_key=''`,
el test debe **sembrar la ventana de reauth para ese key vacío**
(`tests/integration/authz/test_admin_roles.py:46`)::

    def _auth(client, user):
        client.force_authenticate(user)
        ReauthSession.objects.update_or_create(
            user_id=user.pk, session_key='',
            defaults={'started_at': ..., 'expires_at': ...})

Si un endpoint depende de la sesión (reauth, invalidación, `session_key`), usar
`force_login` **o** sembrar el estado como arriba — no basta `force_authenticate`.

## Headers de credenciales — cart token, no JWT Bearer

`client.credentials(**headers)` fija headers para las siguientes requests (**14**
usos). En este proyecto casi siempre es el **cart token** (DEC-BC-07), no auth::

    api_client.credentials(HTTP_X_CART_TOKEN=token)   # carrito anónimo

El `HTTP_AUTHORIZATION=Bearer …` sólo aparece en los tests **dedicados** de los
endpoints JWT (`test_login_logout`, `test_jwt_endpoints`) — SimpleJWT está
instalado pero **dormant** para el default auth (ver `authentication.md`). No usar
`credentials(HTTP_AUTHORIZATION=Bearer …)` para "autenticar" un test de un endpoint
normal; eso lo hace `force_login`. `client.credentials()` sin args limpia los
headers (útil entre fases de un test).

## Assert de la respuesta — `response.data` + status

Assert sobre `response.data` (el dict antes de renderizar), no sobre
`response.content` parseado. El status va con la constante de DRF cuando el test es
nuevo (`status.HTTP_201_CREATED`; ver `status-codes.md`), y el contrato de error se
verifica por **`codigo_error`**, no por el texto de `detail` (ver `exceptions.md`)::

    resp = auth_client.post(url, {'x': 1}, format='json')
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert resp.data['codigo_error'] == 'INVALID_ORDERING'

Con `APIRequestFactory` (vista directa) la respuesta **no está renderizada**: llamar
`response.render()` antes de tocar `response.content`.

## Qué NO se usa

- `APITestCase`/`APITransactionTestCase`/`APISimpleTestCase`/`URLPatternsTestCase`:
  0. El proyecto es pytest-django; no introducir clases xUnit.
- `RequestsClient` / live tests: 0. Los flujos end-to-end reales van por
  **Playwright** en `ui/e2e` (ver `ui-documentacion-en-implementacion.md`), no por
  `RequestsClient`.
- `client.login(username, password)`: 0 — se usa `force_login(user)` (más directo,
  no pasa por el form de login).
- `TEST_REQUEST_DEFAULT_FORMAT` / `TEST_REQUEST_RENDERER_CLASSES` en settings: 0
  (por eso `format='json'` es explícito).
- SQLite: prohibido; la suite corre contra MariaDB (`test-execution-protocol.md`).

## Checklist al escribir un test de endpoint

1. Función `def test_*` + fixture de cliente de `conftest.py`
   (`auth_client`/`admin_client`/`api_client`), no una `APITestCase`.
2. Cuerpo JSON → `format='json'` explícito.
3. ¿Necesita sesión real (reauth, `session_key`)? → `force_login` (fixture
   `auth_client`) o sembrar el estado; **no** sólo `force_authenticate`.
4. ¿Carrito anónimo? → `credentials(HTTP_X_CART_TOKEN=…)`; ¿JWT? → sólo en tests
   dedicados de JWT.
5. Assert `response.data` + status (constante DRF) + `codigo_error` en errores.
6. Correr contra MariaDB (DB por socket + `--reuse-db`), suite del módulo verde
   antes de commitear.

## Referencias cruzadas

- `authentication.md` — auth de sesión (ADR-018); JWT dormant; por qué
  `force_login` es el camino fiel.
- `permissions.md` — `HasCapability`; el reauth DEC-12 que obliga a sembrar la
  ventana con `force_authenticate`.
- `exceptions.md` / `status-codes.md` — assert por `codigo_error` + constante de
  status.
- `throttling.md` — la autouse `clear_rate_limit_cache` evita que el throttle
  contamine tests vecinos.
- `test-execution-protocol.md` (regla) — MariaDB por socket, `--reuse-db`, suite
  completa antes de cerrar.
- Código: `tests/conftest.py:72-104` (fixtures de cliente),
  `tests/integration/authz/test_admin_roles.py:46` (gotcha reauth +
  `force_authenticate`).
```
