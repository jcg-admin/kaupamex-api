```yml
type: Reference (lazy-load on-demand)
applies_when: Se necesita el contrato/esquema del API o se razona sobre la respuesta a OPTIONS
created_at: 2026-07-18 03:17:47
status: Aprobado
version: 1.0.0
source: DRF api-guide/metadata
```

# DRF Metadata (OPTIONS) — no se usa; el contrato es drf-spectacular

> La "metadata" de DRF es cómo el API responde a **`OPTIONS`** (nombre,
> descripción, campos, acciones). El proyecto **no** la usa ni la customiza — el
> contrato del API se publica con **OpenAPI (drf-spectacular)**.

## Metadata de OPTIONS — default de DRF, sin customizar

PROVEN 2026-07-18: **0** `DEFAULT_METADATA_CLASS` en settings, **0**
`metadata_class` overrides, **0** subclases de `BaseMetadata`/`SimpleMetadata`,
**0** handlers `OPTIONS`/`api_schema` a medida. Por lo tanto rige el
`SimpleMetadata` de DRF sin cambios: un `OPTIONS` a un endpoint devuelve el
`name`/`description`/`renders`/`parses`/`actions` ad-hoc de DRF. **Superficie
vestigial** — el proyecto no depende de ella.

## El contrato real — drf-spectacular (OpenAPI)

El esquema/contrato del API se sirve con **drf-spectacular**, no con la metadata
de OPTIONS (PROVEN 2026-07-18):

- `DEFAULT_SCHEMA_CLASS = 'drf_spectacular.openapi.AutoSchema'`
  (`config/settings/base.py:269`).
- Superficie publicada (`config/urls.py`): `SpectacularAPIView` en
  **`/api/schema/`** (OpenAPI crudo), `SpectacularSwaggerView` (Swagger UI) y
  `SpectacularRedocView` (Redoc).
- Cada endpoint anota su contrato con **`@extend_schema`** (no el `@schema`
  nativo de DRF; ver `SKILL.md` Phase 10 y `views.md`).

Consecuencia: un cliente que necesite el contrato **machine-readable** consume
`/api/schema/` (OpenAPI), no un `OPTIONS`. Además, las respuestas `OPTIONS` **no
son cacheables**, otra razón para no apoyar el contrato en ellas.

## Cuándo tocar la metadata — casi nunca

No se necesita una metadata class a medida: el rol que la doc de DRF sugiere para
ella (exponer schema en un `GET`, JSON-schema para el frontend) ya lo cubre
drf-spectacular. **No** subclasear `BaseMetadata` ni montar un endpoint de schema
por `OPTIONS`/`@action(api_schema)`; apuntar al `/api/schema/` de spectacular. Si
en un futuro se quisiera **restringir** lo que un `OPTIONS` revela (p. ej.
`MinimalMetadata` con sólo nombre/descripción), sería la única razón — hoy no
aplica.

## Checklist

1. ¿Contrato del API para un cliente/frontend? → `/api/schema/` (OpenAPI,
   drf-spectacular), **no** `OPTIONS`.
2. ¿Documentar un endpoint? → `@extend_schema` (ver `SKILL.md` Phase 10).
3. **No** subclasear `BaseMetadata` ni customizar `OPTIONS` sin una necesidad
   concreta (restringir lo revelado) — es superficie no usada.

## Referencias cruzadas

- `SKILL.md` Phase 10 — `@extend_schema` en cada endpoint (drf-spectacular).
- `views.md` — por qué se usa `@extend_schema`, no el `@schema` nativo de DRF.
- `renderers.md` / `content-negotiation.md` — `renders`/`parses` que un `OPTIONS`
  reportaría salen de esos policy attributes.
- Código: `config/settings/base.py:269` (`DEFAULT_SCHEMA_CLASS`),
  `config/urls.py:25-37` (`/api/schema/` + Swagger + Redoc).
```
