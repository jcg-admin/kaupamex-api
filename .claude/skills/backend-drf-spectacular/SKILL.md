```yml
name: backend-drf-spectacular
description: "Skill de tecnología para drf-spectacular (OpenAPI 3) en el backend de e-commerce (submódulo api). Usar cuando se documenta el contrato de un endpoint, se añade una app al schema, se corrige un warning de generación, o se toca SPECTACULAR_SETTINGS. Cubre: el patrón Open/Closed (base.py cerrado + schema.py por app), @extend_schema por endpoint, tags por app, ENUM_NAME_OVERRIDES, extensiones (auth/serializer/view) y la superficie /api/schema/. Invocar en Phase 7 DESIGN/SPECIFY para el contrato del endpoint y Phase 11 TRACK/EVALUATE para verificar el schema."
layer: backend
framework: drf-spectacular
project: e-comerce
allowed-tools: Read Glob Grep Bash
stack:
  - Python 3.12+
  - Django 6.0.x
  - djangorestframework 3.16.x
  - drf-spectacular 0.29.0
```

# drf-spectacular — SKILL

Guía fase-por-fase para el **contrato OpenAPI 3** del submódulo `api`
(`src/addons/**`). Complementa el skill `backend-drf` (que cubre la vista); este
cubre **cómo esa vista se documenta** en el schema. El detalle vive en
`references/` (on-demand).

> **Regla base:** el schema **nativo** de DRF NO se usa; el contrato lo genera
> **drf-spectacular** (`DEFAULT_SCHEMA_CLASS='drf_spectacular.openapi.AutoSchema'`,
> `base.py:269`). Ver `backend-drf/references/schema.md`.

---

## Stage 3: DIAGNOSE — Antes de tocar el schema

- ¿El cambio documenta **un endpoint** (contrato de request/response) o afecta la
  **config global** (título, auth, generación)? Determina dónde va (abajo,
  Open/Closed).
- ¿Introduce un **enum** (choices de modelo/serializer)? → riesgo de colisión de
  nombre → `ENUM_NAME_OVERRIDES` (ENUM_NAME_OVERRIDES; ver `references/spectacular-settings.md` §enums — referencia dedicada por pieza).
- ¿La introspección automática **falla** (login, logout, respuesta a medida)? →
  extensión en el `schema.py` de la app (extensión en `schema.py`; ver `references/spectacular-settings.md` §hooks — referencia dedicada por pieza).
- ¿Es una **app nueva**? → su `schema.py` con `SPECTACULAR_TAGS` — NUNCA tocar
  `base.py` para añadir un tag (Open/Closed).

## Principio rector — Open/Closed (`config/spectacular_hooks.py`)

El setup separa lo **cerrado** de lo **abierto** (PROVEN 2026-07-18):

- **CERRADO — `config/settings/base.py`:** `SPECTACULAR_SETTINGS` lleva **solo**
  config global inmutable (título, versión, auth, comportamiento del generador,
  `ENUM_NAME_OVERRIDES`). **No se toca** al añadir apps.
- **ABIERTO — `src/addons/<app>/schema.py`:** cada app declara sus `SPECTACULAR_TAGS`
  y sus extensiones. Dos hooks propios los recogen:
  - `register_app_schema_extensions` (**PREPROCESSING**) — importa los `schema.py`
    **antes** de generar, para que las extensiones (p.ej. `CsrfExemptSessionScheme`)
    se auto-registren a tiempo (si no, el `securityScheme cookieAuth` de ADR-018 no
    se resuelve y drf-spectacular emite "could not resolve authenticator").
  - `collect_app_tags` (**POSTPROCESSING**) — agrega los `SPECTACULAR_TAGS` de cada
    app al schema final.

**Consecuencia dura:** añadir un dominio (catalogue, orders, …) **nunca** requiere
editar `base.py` — solo crear su `schema.py`. **24** apps ya siguen el contrato
(PROVEN: 24 `schema.py`, 24 con `SPECTACULAR_TAGS`).

## Phase 7: DESIGN/SPECIFY — El contrato de un endpoint

Cada endpoint anota su contrato con **`@extend_schema`** (**354** usos PROVEN),
no el `@schema` nativo de DRF. Mínimo recomendado::

    @extend_schema(
        summary='Ver catálogo de productos',
        parameters=[OpenApiParameter('category', str),
                    OpenApiParameter('ordering', OpenApiTypes.STR)],
        responses={200: ProductListSerializer(many=True), 404: None},
        tags=['catalogue'],
    )
    def get(self, request, *args, **kwargs):
        ...

Utilidades en uso (PROVEN 2026-07-18, `src/addons`):

| Util | Usos | Para qué |
|---|---|---|
| `@extend_schema` | 354 | contrato de la operación (summary, params, responses, tags) |
| `OpenApiResponse` | 135 | describir una respuesta (éxito **o** error con `codigo_error`) |
| `OpenApiParameter` | 108 | query/path params (los del filtrado manual, ver `backend-drf/references/filtering.md`) |
| `OpenApiTypes` | 102 | tipar params/campos (`OpenApiTypes.DECIMAL`, `.STR`, `.UUID`…) |
| `extend_schema_field` | 72 | tipar un `SerializerMethodField` (ver `backend-drf/references/serializer-fields.md`) |
| `inline_serializer` | 44 | forma request/response a medida sin crear un serializer real |

**No** se usa (PROVEN: 0): `@extend_schema_view`, `OpenApiExample`,
`extend_schema_serializer`, `PolymorphicProxySerializer`. No introducirlos sin
necesidad — el estilo actual anota **en el método** de la vista.

Reglas del contrato:

1. `tags=['<app>']` **siempre** — el tag debe existir en el `SPECTACULAR_TAGS` de
   esa app (si no, el tag sale sin descripción).
2. Documentar **el error** cuando el endpoint tiene uno codificado:
   `responses={..., 409: OpenApiResponse(...)}` — el cuerpo lleva `codigo_error`
   (ver `backend-drf/references/exceptions.md`).
3. Endpoint deprecado → `deprecated=True` + `summary` con el destino
   (`'[DEPRECATED → /api/v2/products/] …'`, patrón real de `catalogue/views.py`).
4. Un `SerializerMethodField` sin tipo inferible → `@extend_schema_field` en el
   serializer, no un `OpenApiParameter` en la vista.

## Phase 7 (cont.): cuando la introspección automática falla

Si drf-spectacular no puede introspeccionar (un `validate()` que cambia la forma,
un serializer de terceros como simplejwt, una respuesta 200 vacía), la solución
es una **extensión en el `schema.py` de la app** (auto-registrada por
`__init_subclass__` al definir la clase; el PREPROCESSING hook garantiza el
import a tiempo). Tres tipos en uso (`addons/users/schema.py`, PROVEN):

- `OpenApiAuthenticationExtension` → `CsrfExemptSessionScheme` (documenta la auth
  de sesión como `cookieAuth`, ADR-018).
- `OpenApiSerializerExtension` → `PYTokenObtainPairSerializerExtension` (fija la
  forma request/response del login, que el `validate()` override rompe).
- `OpenApiViewExtension` → `TokenBlacklistViewFix` (documenta el logout de
  simplejwt, respuesta 200 vacía).

Detalle + plantillas: referencia dedicada `per-app-schema` (por pieza); patrón resumido arriba.

## Phase 11: TRACK/EVALUATE — Verificar el schema

- **Generar sin warnings** (el gate real de esta capa). Como
  `ENABLE_DJANGO_DEPLOY_CHECK` es default-`True`, la generación corre en el deploy
  check (PROVEN 2026-07-18, exit 0 sin warnings de spectacular)::

      cd /home/user/e-commerce-api && \
        DJANGO_SETTINGS_MODULE=config.settings.testing \
        uv run python manage.py check --deploy 2>&1 | grep -iE "spectacular|schema|W"

  Un `Warning: … could not resolve …` señala una introspección fallida
  (falta extensión) o un enum sin override. Para el schema crudo completo:
  `manage.py spectacular --file /tmp/schema.yml` (este **no** es gate — a mano al
  iterar). Detalle en `references/spectacular-settings.md`.
- **Superficie publicada** (`config/urls.py`, PROVEN): `/api/schema/`
  (`SpectacularAPIView`), `/api/schema/swagger-ui/` (Swagger),
  `/api/schema/redoc/` (Redoc). Un cliente consume el `/api/schema/`, no `OPTIONS`.
- Enum nuevo con nombre colisionado → `Warning: encountered multiple names for
  the same choice set` → añadir a `ENUM_NAME_OVERRIDES` (ver
  `references/spectacular-settings.md` §enums; referencia dedicada por pieza).

## Qué NO cambia (invariantes)

- El schema nativo de DRF (`rest_framework.schemas`/`@schema`): no se usa.
- El **cuerpo de error** lo sella el `EXCEPTION_HANDLER` central con `codigo_error`
  — el schema lo **documenta**, no lo altera (ver `backend-drf/references/exceptions.md`).
- El identificador del modelo LLM NO va en commits/artefactos.

## Referencias on-demand (`references/`)

El skill crece por pieza de la doc de drf-spectacular (mismo patrón que
`backend-drf`). Existentes:

- [`spectacular-settings.md`](references/spectacular-settings.md) — el bloque
  `SPECTACULAR_SETTINGS` (cerrado) + defaults heredados + gate `check --deploy` +
  los 2 hooks Open/Closed; qué se fija y por qué.
- [`customization.md`](references/customization.md) — los **7 pasos** para acercar
  el schema a la API (queryset/serializer → `@extend_schema` → `@extend_schema_field`
  → extensiones → hooks), mapeados al proyecto: qué se usa (3 extensiones) y qué
  **no** (`@extend_schema_view`/`@extend_schema_serializer`/field-ext/filter-ext = 0);
  la desviación de `ready()` (PREPROCESSING hook por el gate no-lazy) y el gotcha
  de re-añadir el enum hook.
- [`client-generation.md`](references/client-generation.md) — el proyecto **no**
  genera cliente (UI a mano); el schema es para documentar. `COMPONENT_SPLIT_REQUEST`
  ya está (por precisión, no por generador); los knobs de compatibilidad
  (`COMPONENT_NO_READ_ONLY_REQUIRED`, `ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE`,
  `GENERIC_ADDITIONAL_PROPERTIES`) se dejan en su default preciso; gap: el gate CI
  `--validate --fail-on-warn` no está cableado.
- [`faq-troubleshooting.md`](references/faq-troubleshooting.md) — índice de síntomas
  → manejo del proyecto: ya resuelto (versioning off ⇒ nada faltante, `{format}`
  excluido, extensiones por PREPROCESSING no `ready()`); gotchas que aplican
  (`@extend_schema` en el `get`/`post` de un `APIView`, `@api_view` multi-método,
  `@action` paginado); CSP en blanco (no aplica en Django, caveat prod); y los
  mecanismos disponibles-pero-no-usados (Polymorphic/enveloper/`swagger_fake_view`…).

Próximas (una por pieza de la doc): el contrato del `schema.py` por app
(`SPECTACULAR_TAGS` + extensiones auth/serializer/view), patrones de
`@extend_schema` por endpoint, y `ENUM_NAME_OVERRIDES`. Mientras tanto, sus
patrones están resumidos inline en las fases de arriba (Open/Closed, Phase 7).

## Referencias cruzadas (skill `backend-drf`)

- `backend-drf/references/schema.md` — por qué spectacular y no el schema nativo.
- `backend-drf/references/serializer-fields.md` — `extend_schema_field`.
- `backend-drf/references/exceptions.md` — `codigo_error` que el schema documenta.
- `backend-drf/references/settings.md` — `DEFAULT_SCHEMA_CLASS` en el bloque
  `REST_FRAMEWORK`.
- Código: `config/settings/base.py` (`SPECTACULAR_SETTINGS`),
  `config/spectacular_hooks.py` (hooks), `addons/users/schema.py` (extensiones),
  `config/urls.py:25-37` (superficie publicada).
```
