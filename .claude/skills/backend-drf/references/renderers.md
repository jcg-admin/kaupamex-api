```yml
type: Reference (lazy-load on-demand)
applies_when: Un endpoint devuelve algo distinto de JSON (CSV/PDF/XLSX export) y hay que fijar renderer_classes o escribir un renderer a medida
created_at: 2026-07-18 02:55:44
status: Aprobado
version: 1.0.0
source: DRF api-guide/renderers
```

# DRF Renderers — cómo se serializa la respuesta

> El **cómo construir** la respuesta vive en `response-object.md`. Este doc es el
> **renderer**: la clase que convierte `response.data` en el byte-stream final
> según el `Accept` del cliente (content negotiation).

## Default del proyecto — JSON, sin browsable en producción

`DEFAULT_RENDERER_CLASSES` está **fijado a sólo JSON** (PROVEN 2026-07-18,
`src/config/settings/base.py:266-268`)::

    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],

Decisión deliberada: el API de producción **no** expone el `BrowsableAPIRenderer`
(la interfaz HTML navegable). Es un API-only endurecido. En **desarrollo** sí se
añade el browsable (PROVEN, `src/config/settings/development.py:8-11`)::

    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ]

Implicación: la inmensa mayoría de los endpoints devuelve JSON y **no** toca
`renderer_classes`. `JSONRenderer` produce UTF-8 compacto; el cliente puede pedir
`Accept: application/json; indent=4` para indentar.

## Content negotiation — cómo se elige el renderer

Al entrar a la vista, DRF hace content negotiation: examina el header **`Accept`**
(y opcionalmente el sufijo de formato en la URL, p. ej. `.csv`) y elige el
renderer cuyo `media_type` mejor satisface la petición. Si el cliente no
especifica (`Accept: */*` o sin header), gana el **primero** de la lista — por eso
el orden importa y `JSONRenderer` va primero.

## Cuándo fijar `renderer_classes` — exports binarios

Se overridea sólo cuando el endpoint sirve un formato no-JSON. Estado del repo
(PROVEN 2026-07-18): **1** override de `renderer_classes` en `src/addons`, **0**
decoradores `@renderer_classes` (FBV).

El caso real es el módulo de reportes, que ofrece el mismo endpoint en varios
formatos por content negotiation (`reports/views.py:314`)::

    renderer_classes = [JSONRenderer, _CSVRenderer, _XLSXRenderer, _PDFRenderer]

El cliente elige el formato con el `Accept` (o el sufijo). `JSONRenderer` primero
= default cuando no se especifica.

## Renderer a medida — 3 en el repo (reportes)

Un renderer propio subclasea `BaseRenderer`, fija `.media_type` + `.format` e
implementa `render(self, data, accepted_media_type, renderer_context)`
devolviendo el byte-stream del body. Estado del repo (PROVEN 2026-07-18): **3**
subclases de `BaseRenderer`, todas en `reports/views.py`:

| Clase | `media_type` | `format` |
|---|---|---|
| `_CSVRenderer` (`:175`) | `text/csv` | `csv` |
| `_PDFRenderer` (`:183`) | `application/pdf` | `pdf` |
| `_XLSXRenderer` (`:191`) | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `xlsx` |

Cada uno devuelve `data` tal cual si ya es `bytes`/`str`. Es el patrón nativo del
proyecto para exports tabulares/binarios servidos por content negotiation, sin
deps de terceros (`drf-excel`, `djangorestframework-csv`).

**Guía para un renderer binario nuevo (PDF/XLSX/imagen):** la doc de DRF
recomienda fijar `charset = None` y `render_style = 'binary'` en la clase, para
que `Response` no fuerce un charset en el `Content-Type` y el browsable no intente
mostrar el binario como texto. Los tres renderers actuales del repo **no** fijan
esos dos atributos (PROVEN 2026-07-18: sólo `media_type` + `format` en
`reports/views.py:175-197`); funcionan porque devuelven bytes, pero un renderer
binario nuevo debería incluirlos.

## Alternativa: `StreamingHttpResponse`/`FileResponse` para descargas grandes

Para descargas grandes o streaming, el proyecto también usa
`StreamingHttpResponse`/`FileResponse` de Django directamente (no un renderer) —
ver `response-object.md` (`reports/exports.py:48`, `reports/views.py:508`). El
renderer a medida encaja cuando el mismo endpoint negocia varios formatos; el
`StreamingHttpResponse` cuando es una descarga directa que no pasa por content
negotiation.

## HTML / plantillas — no se usan

`TemplateHTMLRenderer`, `StaticHTMLRenderer`, `AdminRenderer`, `HTMLFormRenderer`
**no** se usan (0 referencias en `src/addons`, PROVEN 2026-07-18). El proyecto es
API-only; la capa HTML es la UI React separada. No introducir renderers de
plantilla ni deps de terceros (YAML/XML/JSONP/msgpack) sin un media type nuevo que
el API deba servir de verdad.

## Checklist al devolver algo que no es JSON

1. ¿La respuesta es JSON? → no tocar nada (el default lo renderiza).
2. ¿Export tabular/binario negociado por formato (CSV/PDF/XLSX)? → renderer a
   medida `BaseRenderer` (patrón de `reports/views.py`), con `JSONRenderer`
   primero en la lista. Si es binario nuevo, fijar `charset=None` +
   `render_style='binary'`.
3. ¿Descarga directa grande? → `StreamingHttpResponse`/`FileResponse` (ver
   `response-object.md`), no un renderer.
4. No añadir `BrowsableAPIRenderer` a producción — está deshabilitado a
   propósito; sólo vive en `development.py`.

## Referencias cruzadas

- `response-object.md` — construir la `Response`; excepción streaming/`FileResponse`.
- `request-object.md` / `parsers.md` — el lado de entrada (`Content-Type` →
  parser); este doc es el lado de salida (`Accept` → renderer).
- `views.md` — `renderer_classes` como policy attribute + su decorador FBV.
- Código: `src/config/settings/base.py:266` (default JSON), `development.py:8`
  (browsable en dev), `addons/reports/views.py:175-314` (renderers a medida).
```
