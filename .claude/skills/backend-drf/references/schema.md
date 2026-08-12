```yml
type: Reference (lazy-load on-demand)
applies_when: Se documenta el contrato OpenAPI de un endpoint o se razona sobre el schema del API
created_at: 2026-07-18 03:20:44
status: Aprobado
version: 1.0.0
source: DRF api-guide/schema
```

# DRF Schema — el schema nativo NO se usa; el contrato es drf-spectacular

> El `rest_framework.schemas` de DRF (`AutoSchema`/`ManualSchema`/`@schema`) está
> **deprecado** en la propia doc de DRF, que remite a bibliotecas externas. El
> proyecto sigue esa recomendación: el contrato OpenAPI lo genera
> **drf-spectacular**, no la maquinaria de schema nativa.

## El schema nativo de DRF está DESACTIVADO

PROVEN 2026-07-18: **0** referencias a `rest_framework.schemas` /
`from rest_framework.schemas` / `@schema` (el decorador nativo) / `AutoSchema` de
DRF en `src/` (la búsqueda excluye `drf_spectacular`). Por lo tanto:

- **No** se usa `get_schema_view()` de DRF, ni `ManualSchema`, ni `coreapi`.
- El `AutoSchema` que sí rige es el de **spectacular**, cableado en settings
  (ver abajo) — no el homónimo de `rest_framework.schemas.openapi`.

## El contrato real — drf-spectacular (OpenAPI 3)

El `DEFAULT_SCHEMA_CLASS` apunta a spectacular (PROVEN 2026-07-18,
`config/settings/base.py:269`)::

    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',

`SPECTACULAR_SETTINGS` (`config/settings/base.py:347`) fija los metadatos del
contrato:

- `TITLE`: ``'Kaupamex API'`` · `VERSION`: ``'1.0.0'`` · `LICENSE`:
  ``'Propietario'``. (PROVEN 2026-08-12, `base.py:495` — decisión de producto
  del ejecutor 2026-08-05 cambió el valor desde `'PracticaYoruba API'`;
  guardado por regresión en `tests/integration/test_schema.py`.)
- `DESCRIPTION`: declara la **auth de sesión** (cookie HttpOnly via
  ``POST /api/v2/auth/login/``) y el prefijo ``/api/v2/`` — coherente con
  `authentication.md` y `versioning.md`.
- `CONTACT`: ``'Equipo Kaupamex' / 'soporte@kaupamex.com'`` — es el **operador
  L0 de la plataforma**, no el buzón del L1 de ejemplo. El schema es infraestructura
  de plataforma (un solo codebase Django sirve a todas las Company), evaluada
  estáticamente al generar — sin dimensión de empresa (DEC-KX-05, follow-up
  #199). El `TITLE`/`DESCRIPTION` nombran al operador L0 (Kaupamex), no al L1
  de ejemplo (PracticaYoruba); cambiarlos es decisión de producto aparte, no de
  clasificación de config.
- `SERVE_PUBLIC: True` + `SERVE_PERMISSIONS: ['AllowAny']`: el schema se sirve
  público. `SERVE_INCLUDE_SCHEMA: False`: el propio `/api/schema/` no aparece
  dentro del schema.

## Superficie publicada

El contrato machine-readable y sus UIs viven en `config/urls.py` (PROVEN
2026-07-18):

- ``/api/schema/`` — `SpectacularAPIView` (OpenAPI 3 crudo, `name='schema'`).
- ``/api/schema/swagger-ui/`` — `SpectacularSwaggerView` (Swagger UI).
- ``/api/schema/redoc/`` — `SpectacularRedocView` (Redoc).

Un cliente/frontend que necesite el contrato consume ``/api/schema/`` — **no** un
`OPTIONS` (ver `metadata.md`) ni el schema nativo de DRF.

## Anotación por endpoint — `@extend_schema`, no `@schema`

El schema se afina endpoint por endpoint con los decoradores de spectacular
(PROVEN 2026-07-18, `src/addons`):

| Decorador / util | Usos | Para qué |
|---|---|---|
| `@extend_schema` | 354 | contrato de la operación (request/response, params, tags) |
| `tags=[...]` | 273 | agrupar la operación en la UI por dominio |
| `OpenApiResponse` | 135 | describir respuestas (incluye los de error con `codigo_error`) |
| `OpenApiParameter` | 108 | query/path params (los del filtrado manual, ver `filtering.md`) |
| `OpenApiTypes` | 102 | tipar params/campos en el schema |
| `extend_schema_field` | 72 | tipar un `SerializerMethodField` (ver `serializer-fields.md`) |

**Nunca** el `@schema` nativo de DRF. `@extend_schema_view` y `OpenApiExample`:
**0** usos (PROVEN 2026-07-18) — no forman parte del estilo actual; el contrato
se anota directo en el método/vista, sin ejemplos embebidos.

## Por qué spectacular y no el schema nativo

La doc de DRF marca su propio generador de schema como **deprecado** y remite a
externos; spectacular es el estándar de facto para OpenAPI 3 en DRF. Ventaja
concreta aquí: introspecciona los serializers explícitos del proyecto (fields
declarados, `source=`, `SerializerMethodField` tipado con `extend_schema_field`)
y produce un OpenAPI 3 fiel sin schema classes a mano. El schema nativo
(`coreapi`, OpenAPI 2) no cubriría el contrato de error `codigo_error` ni el
tipado de los method fields con la misma limpieza.

## Checklist al documentar un endpoint

1. ¿Contrato de la operación? → `@extend_schema(...)` con `tags=[...]`,
   `OpenApiResponse` (éxito **y** error `codigo_error`), `OpenApiParameter` para
   los query params del `get_queryset()`.
2. ¿Un `SerializerMethodField` sin tipo inferible? → `@extend_schema_field`
   (ver `serializer-fields.md`).
3. ¿Servir/consumir el contrato? → ``/api/schema/`` (o Swagger/Redoc), **no**
   el schema nativo ni `OPTIONS`.
4. **No** usar `@schema`, `AutoSchema`/`ManualSchema` de `rest_framework.schemas`,
   ni `get_schema_view()` — es superficie deprecada y apagada.

## Referencias cruzadas

- `metadata.md` — el contrato va por `/api/schema/`, no por `OPTIONS`; misma
  superficie publicada (Swagger/Redoc).
- `serializer-fields.md` — `extend_schema_field` para tipar `SerializerMethodField`.
- `filtering.md` — los `OpenApiParameter` documentan los query params del
  filtrado manual en `get_queryset()`.
- `authentication.md` / `versioning.md` — el `DESCRIPTION` del schema declara la
  auth de sesión y el prefijo `/api/v2/`.
- `SKILL.md` Phase 10 — `@extend_schema` en cada endpoint (drf-spectacular).
- Código: `config/settings/base.py:269` (`DEFAULT_SCHEMA_CLASS`), `:347`
  (`SPECTACULAR_SETTINGS`), `config/urls.py:25-37` (`/api/schema/` + Swagger +
  Redoc).
```
