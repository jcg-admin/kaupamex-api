```yml
type: Reference (lazy-load on-demand)
applies_when: Se elige un OpenApiTypes/location para un parámetro, se documenta un summary/description, o se encuentra un snippet de drf-yasg
created_at: 2026-07-18 03:53:47
status: Aprobado
version: 1.0.0
source: drf-spectacular "From drf-yasg to OpenAPI 3"
```

# OpenApiTypes + docstrings (y por qué NO hay migración drf-yasg)

> El proyecto **no** usa drf-yasg (OpenAPI 2.0) — nació con drf-spectacular
> (OpenAPI 3), así que **no hay migración**. De esta pieza sirve el catálogo de
> `OpenApiTypes` que el proyecto usa, el manejo de docstrings, y un mapa por si
> aparece un snippet de yasg copiado de un ejemplo.

## drf-yasg NO está — no migrar nada

PROVEN 2026-07-18: **0** `drf-yasg`/`drf_yasg`/`@swagger_auto_schema` en el repo.
No hay `Parameter`/`Response`/`Schema`/`TYPE_*`/`IN_*` de yasg que traducir. Si
apareciera un snippet de yasg (copiado de un blog), el equivalente directo es:
`@swagger_auto_schema`→`@extend_schema`, `manual_parameters`/`query_serializer`→
`parameters`, `request_body`→`request`, `Parameter(in_=…)`→`OpenApiParameter(location=…)`,
`Response(schema=…)`→`OpenApiResponse(response=…)`, `TYPE_*`/`FORMAT_*`→`OpenApiTypes.*`.

## `OpenApiTypes` — el catálogo que el proyecto usa

Los tipos van en `OpenApiParameter(...)` y en `responses`. **102** usos totales;
distribución PROVEN 2026-07-18 (`src/addons`):

| `OpenApiTypes.` | Usos | Tipo Python equivalente (también aceptado) |
|---|---|---|
| `STR` | 34 | `str` |
| `OBJECT` | 25 | `dict` |
| `INT` | 8 | `int` |
| `BOOL` | 8 | `bool` |
| `DECIMAL` | 6 | `Decimal` (dinero — coherente con `COERCE_DECIMAL_TO_STRING`) |
| `BINARY` | 4 | `bytes` (export/descarga; ver `backend-drf/references/renderers.md`) |
| `URI` | 3 | — |

**Nota:** para tipos básicos, un **hint de Python** basta (`str`, `int`, `bool`,
`Decimal`, `datetime`, `UUID`) — no siempre hace falta `OpenApiTypes`. El proyecto
prefiere `OpenApiTypes.*` explícito por legibilidad. Otros disponibles no usados
hoy: `DATE`/`DATETIME`/`TIME`, `UUID`, `EMAIL`, `IP4`/`IP6`, `DURATION`, `ANY`,
`NONE`.

## Localización de parámetros — `QUERY` por default, `PATH` explícito

`OpenApiParameter(name, type, location)`. PROVEN 2026-07-18: solo **3**
`OpenApiParameter.PATH` explícitos; el resto son **query params** (el `location`
default es `QUERY`, no hace falta ponerlo). Constantes: `PATH`, `QUERY`, `HEADER`,
`COOKIE`. Para body/form no hay constante — se usa
`@extend_schema(request={"<media-type>": ...})`. Los query params documentados
corresponden al filtrado manual (`backend-drf/references/filtering.md`).

## Docstrings vs `summary`/`description` — GOTCHA

drf-spectacular usa **el docstring completo** como `description` (a diferencia de
yasg, que partía la primera línea como summary). Además `DISABLE_DOCSTRING_DESCRIPTIONS`
es default `False` (0 override PROVEN) → **los docstrings SÍ entran al schema**.

**El proyecto lo sortea con `summary=` explícito** — **285** `summary=` en
`@extend_schema` (PROVEN). Regla:

- Poner **siempre** `summary='…'` en el `@extend_schema` (título corto de la
  operación). No confiar en "la primera línea del docstring" (no existe ese split
  aquí).
- Si se quiere `description`, o ponerlo explícito, o dejar que el docstring del
  método la pueble (entra completo).
- **No** dejar un docstring interno/de implementación como description pública sin
  querer — si el docstring es para el desarrollador, poner `summary`/`description`
  explícitos y asumir que el docstring igual entra (o togglear
  `DISABLE_DOCSTRING_DESCRIPTIONS` globalmente, hoy no se hace).
- yasg soportaba "named sections" (`list:`/`retrieve:` en el docstring de la
  clase) — **no** existe aquí; se usa `@extend_schema` por método (o
  `@extend_schema_view`, hoy 0).

## Nombre de componentes — automático

yasg usaba `ref_name` en el `Meta` del serializer; el equivalente es
`@extend_schema_serializer(component_name=…)`. El proyecto **no** lo usa (0, ver
`customization.md`): los nombres de componente se derivan **automáticamente** del
nombre del serializer, y las colisiones de **enum** se fijan con
`ENUM_NAME_OVERRIDES` (referencia `enum-overrides`, por pieza), no con `ref_name`.

## Checklist al documentar params/tipos

1. Tipo de un param/response → `OpenApiTypes.<X>` (o el tipo Python básico).
2. Query param → `OpenApiParameter(name, OpenApiTypes.X)` (location default QUERY);
   path → `location=OpenApiParameter.PATH`.
3. **Siempre** `summary=` en `@extend_schema`; `description` explícita o vía
   docstring (que entra completo — no hay split de primera línea).
4. **No** buscar equivalentes de yasg — no se usa.

## Referencias cruzadas

- `customization.md` — `@extend_schema`/`@extend_schema_field` (los reemplazos de
  yasg) y por qué `component_name`/`@extend_schema_serializer` = 0.
- `spectacular-settings.md` — `DISABLE_DOCSTRING_DESCRIPTIONS` (default) + enums.
- `backend-drf/references/filtering.md` — los query params que se documentan.
- `backend-drf/references/renderers.md` — `OpenApiTypes.BINARY` en export.
```
