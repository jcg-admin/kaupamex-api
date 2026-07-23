```yml
type: Reference (lazy-load on-demand)
applies_when: Se expone un list endpoint y hay que paginarlo (declarar pagination_class) o se consume el envelope de página
created_at: 2026-07-18 03:13:20
status: Aprobado
version: 1.0.0
source: DRF api-guide/pagination
```

# DRF Pagination — partir listas grandes en páginas

> DRF sólo pagina **automáticamente** en generic views/viewsets. Un `APIView`
> plano debe llamar la API de paginación a mano. Este doc fija cómo el proyecto
> pagina: subclase `PageNumberPagination` **por vista**, envelope default.

## Sin paginación global — cada list endpoint la declara

**No** hay `DEFAULT_PAGINATION_CLASS` ni `PAGE_SIZE` en settings (PROVEN
2026-07-18: 0 hits en `base.py`). Ambos son `None` por default en DRF → **un list
view sin `pagination_class` devuelve el queryset ENTERO**. Consecuencia
operativa: **todo endpoint de lista DEBE declarar `pagination_class`**, o expone
la colección sin cota (riesgo de performance/DoS). Los comentarios de
`voucher/views.py:39` y `catalogue/views.py:657` lo dicen literal ("Sin
`pagination_class` el endpoint devuelve todo").

## Patrón del proyecto — subclase `PageNumberPagination` por dominio

Estado del repo (PROVEN 2026-07-18): **~20** subclases de `PageNumberPagination`,
una por dominio (`CataloguePagination`, `OrderPagination`, `AdminUserPagination`,
`ReturnPagination`, `SubscriberPagination`, …), **todas** `PageNumberPagination`
(0 `LimitOffsetPagination`/`CursorPagination`). El molde canónico
(`catalogue/views.py:164`)::

    class CataloguePagination(PageNumberPagination):
        page_size             = 20             # default por página
        page_size_query_param = 'page_size'    # el cliente puede pedir otro
        max_page_size         = 100            # ...con tope (anti-abuso)

    class CatalogueListView(ListAPIView):
        pagination_class = CataloguePagination

Tres atributos:

- **`page_size`** — tamaño por default (50 usos de `page_size` en el repo).
- **`page_size_query_param = 'page_size'`** — deja al cliente pedir otro tamaño
  (`?page_size=50`).
- **`max_page_size`** — **tope** obligatorio cuando se permite `page_size_query_param`,
  para que el cliente no pida "todo" y reintroduzca el problema que la paginación
  resuelve.

Petición: `?page=4` (`page_query_param` default `page`). El proyecto no usa
`LimitOffset` (offset/limit) ni `Cursor` (cursor opaco para datasets enormes);
`PageNumberPagination` cubre las listas del admin/tienda.

## Envelope de respuesta — default DRF, no se customiza

PROVEN 2026-07-18: **0** overrides de `get_paginated_response` → el cuerpo es el
**estándar de DRF** y es el **contrato con la UI**::

    {
      "count":    1023,
      "next":     "…?page=5",
      "previous": "…?page=3",
      "results":  [ … ]
    }

La UI lee `results` (el array) y `count`/`next`/`previous` para la navegación. No
se envuelve en un `links` anidado ni se emite header `Link` — el envelope plano
se mantiene en todos los endpoints paginados.

## Opt-out — `pagination_class = None`

Para un catálogo **pequeño y fijo** (que no crece) se desactiva con
`pagination_class = None`. PROVEN 2026-07-18: **1** uso
(`authz/admin_views.py:88`). Sólo cuando el tamaño está acotado por diseño; ante
la duda, paginar.

## `APIView` plano — paginar a mano

La paginación automática es sólo de generic views/viewsets. Un `APIView` que
liste debe invocar la API de paginación explícito::

    paginator = MiPagination()
    page = paginator.paginate_queryset(qs, request, view=self)
    return paginator.get_paginated_response(MiSerializer(page, many=True).data)

Relevante porque el proyecto tiene muchos `APIView`/`ViewSet` planos: si listan,
verificar que paginan (a mano o vía `ListModelMixin`).

## Qué NO se usa

- `LimitOffsetPagination`, `CursorPagination`: 0 usos. Si algún día hace falta
  paginar un dataset **enorme** con consistencia (timeline sin duplicados),
  `CursorPagination` con un `ordering` estable/indexado/no-float es la vía — hoy
  no ocurre.
- `get_paginated_response` a medida / header `Link` / `BasePagination` propio: 0.
- Terceros (`drf-extensions` `PaginateByMaxMixin`, `drf-proxy-pagination`): no.

## Checklist al listar

1. ¿Es un list endpoint? → **declarar `pagination_class`** (sin él devuelve todo).
2. Subclase `PageNumberPagination` con `page_size` + `page_size_query_param =
   'page_size'` + **`max_page_size`** (tope obligatorio si se permite el param).
3. No customizar el envelope: la UI espera `{count, next, previous, results}`.
4. ¿Catálogo pequeño y fijo? → `pagination_class = None` (excepción, no default).
5. ¿`APIView` plano que lista? → paginar a mano (`paginate_queryset` +
   `get_paginated_response`).
6. La paginación se aplica **después** del filtrado/orden (ver `filtering.md`).

## Referencias cruzadas

- `generic-views.md` — sólo las genéricas paginan solas; `APIView` a mano.
- `filtering.md` — filtro/orden antes de paginar (`CataloguePagination` convive
  con `CatalogueOrderingFilter`).
- `response-object.md` — el envelope de página es un `Response` con el dict.
- Código: `addons/catalogue/views.py:164` (`CataloguePagination`),
  `addons/authz/admin_views.py:88` (`pagination_class = None`).
```
