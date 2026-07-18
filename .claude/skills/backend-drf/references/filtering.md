```yml
type: Reference (lazy-load on-demand)
applies_when: Se filtra/ordena/busca un list endpoint (por usuario, URL, query params) o se expone ordenamiento al cliente
created_at: 2026-07-18 03:11:31
status: Aprobado
version: 1.0.0
source: DRF api-guide/filtering
```

# DRF Filtering — restringir el queryset de un list endpoint

> El default de un list view es devolver **todo** el queryset. El proyecto lo
> restringe **manualmente en `get_queryset()`** leyendo `query_params` — **no**
> con `DjangoFilterBackend`/`SearchFilter`/`OrderingFilter` de DRF (`django-filter`
> ni siquiera está instalado).

## Patrón del proyecto — filtrado manual en `get_queryset()`

No hay `DEFAULT_FILTER_BACKENDS`, ni `django_filters` en deps, ni
`filterset_fields`/`filterset_class`/`SearchFilter` de DRF (PROVEN 2026-07-18:
0 de cada uno). El filtrado se hace en `get_queryset()` con
`request.query_params.get(...)` — **86** usos de `query_params.get` en `src/addons`.
Es el primer estilo de la doc de DRF (filtrar contra usuario / URL / query params)::

    def get_queryset(self):
        qs = Product.objects.all()
        cat = self.request.query_params.get('category')
        if cat is not None:
            qs = qs.filter(category=cat)
        return qs

- **Contra el usuario** (row-scoping L3): `filter(user=self.request.user)` — es
  seguridad, no comodidad (ver `permissions.md`/`generic-views.md`).
- **Contra la URL**: `self.kwargs['<capture>']`.
- **Contra query params**: aplicar el filtro **sólo si** el param vino
  (`if x is not None`).

## Ordenamiento expuesto — **allowlist**, no campo libre

Cuando el cliente controla el orden, el proyecto usa un **allowlist explícito**,
no los campos del serializer. Único filter backend del repo (PROVEN 2026-07-18:
1 `filter_backends`, 1 subclase `BaseFilterBackend`) —
`catalogue/views.py:141` `CatalogueOrderingFilter`::

    class CatalogueOrderingFilter(BaseFilterBackend):
        ORDERING_MAP = {'novedad': '-created_at', 'precio-asc': 'price', ...}
        def filter_queryset(self, request, queryset, view):
            param = request.query_params.get('ordering', '').strip()
            mapped = self.ORDERING_MAP.get(param)
            if param and mapped is None:
                raise ValidationError({'ordering': ..., 'codigo_error':
                                       'INVALID_ORDERING', 'valores_validos': [...]})
            return queryset.order_by(mapped or *DEFAULT_ORDERING)

Mapea un set fijo de tokens públicos (`novedad`/`precio-asc`/…) a un `order_by`
seguro y **rechaza** lo desconocido con `codigo_error`. Resuelve explícitamente el
riesgo que la doc de DRF advierte con `OrderingFilter` (ordenar contra un campo
sensible como un hash) — mejor un allowlist que `ordering_fields = '__all__'`.
**Nunca** exponer ordenamiento por campo arbitrario del modelo/serializer.

## Filter backend a medida — la vía cuando el filtro se reutiliza

Un backend a medida subclasea `BaseFilterBackend` + `filter_queryset(self,
request, queryset, view)` devolviendo el queryset filtrado; se enchufa con
`filter_backends = [...]`. Es lo correcto cuando el filtro debe **reutilizarse en
varias vistas** o aplicarse transversal (p. ej. un `IsOwnerFilterBackend` global).
Para un filtro puntual de una sola vista, `get_queryset()` es más directo — por
eso el repo tiene sólo 1 backend (`CatalogueOrderingFilter`).

## `SearchFilter` de DRF — no se usa

El único `search_fields` del repo está en `returns/admin.py` — es el **search del
Django admin**, no el `SearchFilter` de DRF (PROVEN 2026-07-18). Una búsqueda de
API se implementa manual en `get_queryset()` (`filter(name__icontains=q)`) o, si
se necesita full-text, con el `FULLTEXT INDEX` de MariaDB — no con
`filters.SearchFilter` (pensado sobre todo para el browsable, que está apagado).

## Filtrado + object lookup

Un filter backend configurado en la vista filtra **también** el `get_object()`
del detalle (un id que no cumple el filtro → 404). Con el patrón manual, el
row-scoping de `get_queryset()` produce el mismo efecto: `get_object()` opera
sobre el queryset ya acotado, así que un objeto ajeno da 404 (no 403) — deseable
para no filtrar existencia.

## Qué NO se usa

- `django-filter`/`DjangoFilterBackend`, `filterset_fields`/`filterset_class`:
  no instalado ni usado. No añadirlo sin una necesidad de filtrado declarativo
  complejo que el `get_queryset()` manual no cubra con claridad.
- `filters.SearchFilter`/`OrderingFilter` de DRF: no se usan (browsable apagado);
  el orden va por allowlist propio, la búsqueda por `get_queryset()`.
- Terceros (`drf-url-filter`, `django-url-filter`, etc.): no.

## Checklist al filtrar un list

1. ¿Por usuario? → `get_queryset()` con `filter(user=self.request.user)`
   (seguridad L3).
2. ¿Por query param? → `query_params.get(x)`; aplicar **sólo si** vino.
3. ¿Ordenamiento expuesto al cliente? → **allowlist** de tokens → `order_by`
   seguro (patrón `CatalogueOrderingFilter`), rechazar lo desconocido con
   `codigo_error`. Nunca campo libre.
4. ¿El filtro se reutiliza en varias vistas? → `BaseFilterBackend` +
   `filter_backends`; si es de una sola vista, `get_queryset()`.
5. ¿Búsqueda? → `get_queryset()` (`icontains` o FULLTEXT MariaDB), no
   `SearchFilter`.

## Referencias cruzadas

- `generic-views.md` — `get_queryset()` (row-scoping + `select_related`/
  `prefetch_related` para el N+1 del filtro).
- `permissions.md` — el filtrado por usuario es la 1ª capa de acceso (queryset).
- `request-object.md` — `request.query_params` (no `request.GET`).
- `pagination.md` — el filtro/orden se aplica antes de paginar.
- Código: `addons/catalogue/views.py:141` (`CatalogueOrderingFilter` — allowlist)
  + `CataloguePagination` (paginación por página en la misma vista).
```
