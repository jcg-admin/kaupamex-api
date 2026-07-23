```yml
type: Reference (lazy-load on-demand)
applies_when: Se añade una librería DRF de terceros cuyo schema sale roto, o se necesita una UI/auth alterna
created_at: 2026-07-18 03:51:55
status: Aprobado
version: 1.0.0
source: drf-spectacular Extension Blueprints
```

# Extension Blueprints — fixes para librerías de terceros

> Los blueprints son extensiones **listas para copiar** que arreglan el schema de
> apps/librerías DRF que no cooperan con la introspección (dj-stripe, oscar-api,
> knox, drf-extra-fields, pydantic, parler, adfs, api-key, polymorphic, UIs
> alternas). Se copian tal cual en el `schema.py` de una app.

## Estado en el proyecto — NINGUNA librería de blueprint está instalada

PROVEN 2026-07-18: **0** de las librerías con blueprint oficial está en
`pyproject.toml`/`uv.lock` (dj-stripe, django-oscar-api, djangorestframework-api-key,
django-rest-knox, drf-extra-fields, pydantic, django-parler-rest, django-auth-adfs,
rest_polymorphic, RapiDoc, Elements, drf-rw-serializers). El pago es **mercadopago
SDK** (no Stripe), auth es **sesión + simplejwt** propio, no hay polimórficos ni
i18n de serializers. **Consecuencia:** hoy no se copia ningún blueprint.

## Los "blueprints propios" del proyecto — su propio stack auth

El proyecto ya escribió **3 extensiones** en `addons/users/schema.py` (PROVEN
2026-07-18) que son, en la práctica, blueprints caseros para su stack de auth —
mismo patrón que el blueprint de **knox** (documentar login/logout de una lib de
auth):

- `CsrfExemptSessionScheme(SessionScheme)` — `OpenApiAuthenticationExtension` que
  documenta la sesión CSRF-exenta como `cookieAuth` (ADR-018). Es **exactamente**
  la vía que el doc recomienda para api-key/adfs: `OpenApiAuthenticationExtension`,
  **no** el setting `SECURITY`.
- `PYTokenObtainPairSerializerExtension` — `OpenApiSerializerExtension` que fija la
  forma request/response del login de simplejwt (análogo al `map_serializer` de los
  blueprints de oscar `Fix6/Fix9`).
- `TokenBlacklistViewFix` — `OpenApiViewExtension` que documenta el logout de
  simplejwt (respuesta 200 vacía; análogo al blueprint de knox `KnoxLogoutView`).

Ver `customization.md` (paso 5) y `per-app-schema` (por pieza).

## `OpenApiAuthenticationExtension` > el setting `SECURITY` (regla)

El blueprint de **api-key** usa `APPEND_COMPONENTS` + `SECURITY` porque esa lib no
tiene entrada en `authentication_classes`. El doc **desaconseja** `SECURITY`
(se anexa a **todos** los endpoints sin importar si aplica). PROVEN 2026-07-18: el
proyecto **no** usa `SECURITY`/`APPEND_COMPONENTS` (0) — resuelve su auth con
`OpenApiAuthenticationExtension` (`CsrfExemptSessionScheme`), la vía robusta. Si un
día se añade una auth de librería sin `authentication_classes`, preferir la
extensión, no `SECURITY`.

## UIs alternas (RapiDoc / Elements) — disponibles, no usadas

Los blueprints de **RapiDoc** y **Elements** dan vistas alternas a Swagger/Redoc.
El proyecto ya sirve **Swagger + Redoc** (`config/urls.py`, ver
`backend-drf/references/schema.md`) — suficiente. No añadir una tercera UI sin una
necesidad concreta; si se añadiera, es una `APIView` con `@extend_schema(exclude=True)`
(para que la propia vista de docs no ensucie el schema) que apunta al `/api/schema/`.

## Read/write serializers — el proyecto NO usa drf-rw-serializers

El blueprint de **drf-rw-serializers** swapea el `AutoSchema` para leer serializers
de read/write separados. El proyecto no usa esa lib: separa lectura/escritura
ramificando `get_serializer_class()` por método/rol (ver
`backend-drf/references/serializers.md`). Con `COMPONENT_SPLIT_REQUEST=True` el
schema ya distingue request/response sin swapear el `AutoSchema` (que además
rompería el `DEFAULT_SCHEMA_CLASS` de spectacular).

## Regla al añadir una librería DRF nueva

1. ¿Su schema sale roto? → **primero** buscar un blueprint oficial (lista de
   drf-spectacular) y copiarlo al `schema.py` de una app.
2. Si no hay blueprint → escribir la extensión siguiendo `customization.md`
   (paso 5), en `schema.py`, **registrada por el PREPROCESSING hook** — el doc
   sugiere `apps.ready()`, pero aquí eso lo bloquea `check_no_lazy_imports` (ver
   `spectacular-settings.md`).
3. Auth de librería → `OpenApiAuthenticationExtension`, **no** `SECURITY`.

## Referencias cruzadas

- `customization.md` — el paso 5 (extensiones) del que los blueprints son ejemplos.
- `per-app-schema` (por pieza) — dónde viven (las 3 extensiones propias).
- `spectacular-settings.md` — por qué el PREPROCESSING hook y no `ready()`.
- `backend-drf/references/schema.md` — Swagger/Redoc ya servidos.
- `backend-drf/references/serializers.md` — read/write por `get_serializer_class`.
- Código: `addons/users/schema.py` (las 3 extensiones propias).
```
