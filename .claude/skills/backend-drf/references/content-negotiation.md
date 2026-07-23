```yml
type: Reference (lazy-load on-demand)
applies_when: Un endpoint sirve varios formatos y hay que controlar cómo DRF elige parser/renderer (o ignorar ?format=)
created_at: 2026-07-18 03:16:20
status: Aprobado
version: 1.0.0
source: DRF api-guide/content-negotiation
```

# DRF Content negotiation — elegir parser/renderer

> La content negotiation elige **una** representación entre varias, según el
> `Content-Type` (parser de entrada) y el `Accept` (renderer de salida). Es el
> motor que conecta `parsers.md` (entrada) con `renderers.md` (salida).

## Default — `DefaultContentNegotiation`, negociación trivial en prod

**No** hay `DEFAULT_CONTENT_NEGOTIATION_CLASS` en settings (PROVEN 2026-07-18) →
rige el `DefaultContentNegotiation` de DRF globalmente. Como el renderer default
de producción es **JSON-only** (ver `renderers.md`), la negociación es un no-op de
facto: siempre gana JSON. El motor sigue dos reglas:

1. Media type más **específico** primero (`application/json; indent=4` >
   `application/json` > `*/*`).
2. A igual especificidad, gana el **orden** de `renderer_classes` /
   `DEFAULT_RENDERER_CLASSES`.

**Gotcha:** DRF **ignora los `q` values** del `Accept` (`;q=0.8`) — no ponderan la
preferencia (decisión de diseño de DRF por el impacto en caché). No esperar
weighting por `q`.

## El único negociador a medida — `_PassthroughNegotiator` (exports)

PROVEN 2026-07-18: **1** `content_negotiation_class` override + **1** subclase —
`_PassthroughNegotiator(DefaultContentNegotiation)` en `reports/views.py:160`,
aplicada en la vista de export (`:313`), la misma que declara
`renderer_classes = [JSONRenderer, _CSVRenderer, _XLSXRenderer, _PDFRenderer]`
(ver `renderers.md`)::

    class _PassthroughNegotiator(DefaultContentNegotiation):
        """Ignora ?format=: la vista de export maneja el formato ella misma;
        no queremos que DRF filtre renderers (y lance Http404) por un query
        string cuyo contrato es de la vista."""
        def select_renderer(self, request, renderers, format_suffix=None):
            if not renderers:
                raise exceptions.NotAcceptable()
            return renderers[0], renderers[0].media_type

Por qué existe: el endpoint de export **es dueño de su formato** (decide CSV/PDF/
XLSX por su propia lógica). El filtrado de DRF por `?format=` / `Accept` lanzaría
**Http404** ante un mismatch; `_PassthroughNegotiator` lo **saltea** y devuelve el
primer renderer con su media type. Es un **subclase de `DefaultContentNegotiation`**
(ajuste puntual), no un `BaseContentNegotiation` desde cero.

## Cuándo tocar la negociación

Casi nunca. Sólo cuando un endpoint **controla su propia representación** y el
filtrado por `Accept`/`?format=` de DRF estorba (el caso export). El patrón
sancionado: subclasear `DefaultContentNegotiation` y overridear `select_renderer`
(o `select_parser`), aplicándolo con `content_negotiation_class` **en esa vista**
— no globalmente. Un `BaseContentNegotiation` desde cero (implementar
`select_parser` **y** `select_renderer`) no se usa y no hace falta.

## Atributos de la petición

Tras negociar, `request.accepted_renderer` / `request.accepted_media_type` dicen
qué se eligió (útil si una FBV varía la salida por media type — patrón raro aquí,
ver `renderers.md`). PROVEN 2026-07-18: uso mínimo (los `accepted_media_type` del
repo son el parámetro del `render()` de los renderers de export, no lógica de
negociación).

## Checklist

1. ¿JSON normal? → no tocar nada (negociación trivial, JSON-only en prod).
2. ¿Endpoint que sirve varios formatos y **decide** el formato él mismo (export)?
   → subclase de `DefaultContentNegotiation` con `select_renderer` passthrough +
   `content_negotiation_class` en esa vista (patrón `reports`).
3. No esperar ponderación por `q` en el `Accept` (DRF la ignora).
4. No implementar un `BaseContentNegotiation` desde cero sin una necesidad que el
   subclaseo de `DefaultContentNegotiation` no cubra.

## Referencias cruzadas

- `parsers.md` — la negociación elige el **parser** por `Content-Type` (entrada).
- `renderers.md` — elige el **renderer** por `Accept` (salida); los renderers de
  export del mismo módulo `reports`.
- `views.md` — `content_negotiation_class` como policy attribute de la vista.
- Código: `addons/reports/views.py:160` (`_PassthroughNegotiator`), `:313`
  (aplicación en la vista de export).
```
