```yml
type: Reference (lazy-load on-demand)
applies_when: Se monta un endpoint que sirve varios formatos o se razona sobre ?format= / sufijos .json en la URL
created_at: 2026-07-18 03:22:21
status: Aprobado
version: 1.0.0
source: DRF api-guide/format-suffixes
```

# DRF Format suffixes — no se usan; `?format=` es contrato del export view

> DRF ofrece **sufijos de formato en la URL** (`users.json`) via
> `format_suffix_patterns`, y como alternativa el **query param** `?format=`
> (`URL_FORMAT_OVERRIDE`). El proyecto **no** usa sufijos `.json`; el `?format=`
> queda default-habilitado pero es un no-op de facto, **salvo** en el export view,
> que se apropia de ese param como su propio contrato.

## Sufijos `.json` en la URL — NO se usan

PROVEN 2026-07-18: **0** `format_suffix_patterns` en `src/`, y **0** vistas con
el kwarg `format=None` en su firma (`def get(self, request, format=...)`). Por lo
tanto:

- **No** hay URLs con sufijo de formato (`/comments.json`, `/comments.html`). El
  versionado y el ruteo son por prefijo de URL + namespace (ver `versioning.md`),
  no por extensión.
- Ninguna vista recibe ni ramifica por el kwarg `format` del sufijo — coherente
  con que el renderer de producción es **JSON-only** (ver `renderers.md`): no hay
  un segundo formato que un sufijo tuviera que seleccionar.

Añadir `format_suffix_patterns` sería contraproducente: la doc de DRF advierte que
**no** desciende a `include(...)` — y el URLconf del proyecto es casi todo
`include('<app>.urls', namespace='<app>_v2')` (ver `routers.md`/`versioning.md`),
así que los sufijos ni siquiera alcanzarían a los endpoints reales.

## `?format=` (query param) — default-habilitado, no-op en prod

**No** hay `URL_FORMAT_OVERRIDE` ni `FORMAT_SUFFIX_KWARG` en settings (PROVEN
2026-07-18) → rige el default de DRF: `URL_FORMAT_OVERRIDE = 'format'`, es decir
`?format=` **está activo** globalmente como selector de renderer. Pero como el
renderer de prod es JSON-only, `?format=json` es lo único que resuelve y cualquier
otro valor daría un mismatch — en la práctica **no se usa** para negociar (la
negociación es trivial, ver `content-negotiation.md`).

## La colisión real — el export view se apropia de `?format=`

El único lugar donde `?format=` **significa algo** es el export de reports, y ahí
**no** es el selector de renderer de DRF sino un **parámetro de contrato** de la
vista (PROVEN 2026-07-18, `reports/views.py:344`)::

    fmt = (request.query_params.get('format') or 'csv').lower()
    if fmt not in ('csv', 'xlsx', 'pdf'):
        return Response(..., status=404)

El contrato del endpoint es ``GET /<slug>/export/?format=csv&period=...``
(`reports/views.py:9`, UC-REP-05). El problema: DRF, por su `URL_FORMAT_OVERRIDE`
default, **interpretaría** ese mismo `?format=csv` como selección de renderer y
lanzaría **Http404** si ningún renderer casa (`reports/views.py:308-309`). Por eso
la vista instala `_PassthroughNegotiator`, que **saltea** el filtrado por
`URL_FORMAT_OVERRIDE`/Accept y deja que la vista lea `?format=` ella misma (ver
`content-negotiation.md`). Es el patrón sancionado cuando un endpoint **es dueño
de su formato**: no desactivar `URL_FORMAT_OVERRIDE` global, sino neutralizarlo
**en esa vista** con el negociador passthrough.

## Consecuencias operativas

1. **Endpoint nuevo** → no montar sufijos `.json`; el ruteo va por prefijo +
   namespace. No añadir `format_suffix_patterns` (no desciende a `include`).
2. **Endpoint que sirve varios formatos y decide el formato él mismo** (export) →
   usar `?format=` como **param de contrato**, y aislar la interpretación de DRF
   con `_PassthroughNegotiator` (patrón `reports`), documentando la colisión.
3. **No** tocar `URL_FORMAT_OVERRIDE`/`FORMAT_SUFFIX_KWARG` global sin necesidad:
   cambiarlo afectaría a todos los endpoints; la neutralización correcta es por
   vista.

## Qué NO se usa

- `format_suffix_patterns` / sufijos `.json`/`.html` en URLs: 0.
- Kwarg `format=None` en firmas de vista: 0.
- `i18n_patterns` + `format_suffix_patterns`: no aplica (sin sufijos).
- Override de `URL_FORMAT_OVERRIDE`/`FORMAT_SUFFIX_KWARG` en settings: 0 (rige el
  default `'format'`, neutralizado por vista donde estorba).

## Checklist

1. ¿URL nueva? → prefijo + namespace, **sin** sufijo de formato.
2. ¿Un solo formato (JSON)? → nada que hacer (JSON-only en prod).
3. ¿Varios formatos y la vista decide? → `?format=` como contrato +
   `_PassthroughNegotiator` en esa vista (no global).
4. **No** montar `format_suffix_patterns` (no desciende a `include`).

## Referencias cruzadas

- `content-negotiation.md` — `_PassthroughNegotiator` que neutraliza
  `URL_FORMAT_OVERRIDE`/Accept en el export; negociación trivial en prod.
- `renderers.md` — JSON-only en prod (por eso no hay segundo formato que un sufijo
  seleccione); los 3 renderers del export (`_CSVRenderer`/`_XLSXRenderer`/`_PDFRenderer`).
- `versioning.md` / `routers.md` — ruteo por prefijo + namespace + `include`
  (donde los sufijos no descenderían).
- Código: `addons/reports/views.py:308-309` (colisión `?format=` vs renderer),
  `:344` (lectura de `?format=` como contrato), `:160` (`_PassthroughNegotiator`).
```
