```yml
type: Reference (lazy-load on-demand)
applies_when: Se crea o modifica una vista DRF (APIView o @api_view) — mecánica, ciclo y policy attributes
created_at: 2026-07-18 02:42:01
status: Aprobado
version: 1.0.0
source: DRF api-guide/views
```

# DRF Views — APIView, FBV, ciclo y policy attributes

> La **decisión de estilo** (FBV vs ViewSet vs CBV) vive en `SKILL.md`
> (Phase 7). Este doc es la **mecánica**: qué hace `APIView`/`@api_view`, el
> ciclo de dispatch, los policy attributes y sus equivalentes FBV.

## Qué añade `APIView`/`@api_view` sobre una vista Django

Ambos garantizan (por eso **toda** vista que devuelva `Response` debe ser una de
las dos):

1. El handler recibe un `Request` de DRF (no `HttpRequest`) — parsing flexible.
2. Puede devolver `Response` — content-negotiation + renderer correcto.
3. Cualquier `APIException` se **atrapa y media** a una respuesta de error.
4. **Antes** de despachar al handler se ejecutan, en orden: autenticación →
   permisos → throttle → content-negotiation (`.initial()`).

## Policy attributes (CBV) ↔ decoradores (FBV)

Los defaults vienen de `settings.REST_FRAMEWORK` (`DEFAULT_AUTHENTICATION_CLASSES`,
`DEFAULT_PERMISSION_CLASSES`, `DEFAULT_THROTTLE_CLASSES`/`_RATES`,
`config/settings/base.py:249-282`). Sólo se overridean cuando el endpoint lo
necesita:

| Aspecto | CBV `APIView` (atributo) | FBV (decorador, **debajo** de `@api_view`) |
|---|---|---|
| Permisos | `permission_classes = [...]` | `@permission_classes([...])` (o `@require_capability` del proyecto) |
| Auth | `authentication_classes = [...]` | `@authentication_classes([...])` |
| Throttle | `throttle_classes = [...]` (+ `throttle_scope`) | `@throttle_classes([...])` |
| Renderers/Parsers | `renderer_classes` / `parser_classes` | `@renderer_classes` / `@parser_classes` |
| Schema OpenAPI | (drf-spectacular) `@extend_schema` sobre la clase/método | `@extend_schema` **arriba** de `@api_view` |

Los decoradores de policy van **después (debajo)** de `@api_view`. El único que va
**arriba** es `@extend_schema` (drf-spectacular).

## FBV — `@api_view` mecánica

- `@api_view(['GET','POST'])`: los métodos NO listados → **405 Method Not
  Allowed**. Sin argumento, sólo `GET`.
- Orden canónico del proyecto (ya usado en `authz_totp`):

      @extend_schema(...)          # drf-spectacular (arriba)
      @api_view(['POST'])
      @require_capability('dom.verbo')   # fija permission_classes (más interno)
      def handler(request): ...

- **NO** usar el `@schema` nativo de DRF — el proyecto usa **drf-spectacular**
  (`@extend_schema`). PROVEN 2026-07-18: 0 usos de `rest_framework.schemas.@schema`.

## Ciclo de dispatch — dónde engancha cada cosa

- **`.initial(request)`** — ejecuta auth + permisos + throttle +
  content-negotiation antes del handler. No se sobrescribe.
- **`.handle_exception(exc)`** — toda excepción del handler pasa por aquí.
  Maneja `APIException`, `Http404` y `PermissionDenied`. **En este proyecto** el
  error se sella centralmente vía `EXCEPTION_HANDLER =
  core.exception_handling.custom_exception_handler` (ADR-019/SOL-011): envuelve al
  handler de DRF y da la forma canónica del error. Por eso **`raise
  AuthenticationFailed(...)` / `ValidationError` / `PermissionDenied` / `NotFound`
  es un patrón válido** (163 usos en el repo) — el handler central los mapea; no
  es necesario construir el 4xx manualmente en cada punto. Coexiste con el
  `return Response({'codigo_error': ...}, status=4xx)` explícito.
- **`.initialize_request` / `.finalize_response`** — envuelven request/response;
  no se sobrescriben.

## Throttling en FBV — la receta (evita la fricción de `throttle_scope`)

`ScopedRateThrottle` lee `view.throttle_scope`, un **atributo de clase** — no
existe en FBV. Para migrar un endpoint con throttle a FBV, subclasar
`UserRateThrottle` con `scope` fijo (la tasa se resuelve de
`DEFAULT_THROTTLE_RATES[scope]`):

```python
from rest_framework.throttling import UserRateThrottle

class ChangePasswordThrottle(UserRateThrottle):
    scope = 'change_password'   # rate desde DEFAULT_THROTTLE_RATES

@extend_schema(...)
@api_view(['POST'])
@throttle_classes([ChangePasswordThrottle])
@require_capability('account.security')
def change_password(request): ...
```

Contexto del repo (PROVEN): `ScopedRateThrottle` + `throttle_scope` en CBV
(`register`, `addresses`, `change_password`, `password_reset` —
`users/views.py`). `testing.py` desactiva `DEFAULT_THROTTLE_CLASSES`. Esta receta
es la que necesita la iniciativa `migrar-self-account-a-fbv`.

## Referencias cruzadas

- `request-object.md` — el `Request` que reciben los handlers.
- `response-object.md` — el `Response` que devuelven.
- `SKILL.md` Phase 7 — decisión FBV / ViewSet / CBV.
- Código: `core/exception_handling.py` (handler central), `config/settings/base.py`
  (defaults DRF), `addons/authz_totp/views.py` (precedente FBV).
