```yml
type: Reference (lazy-load on-demand)
applies_when: Se registra un ViewSet en un router, se elige el basename/prefijo, o se cambia el URL de una @action (url_path)
created_at: 2026-07-18 02:52:50
status: Aprobado
version: 1.0.0
source: DRF api-guide/routers
```

# DRF Routers — cableado automático de URLs del ViewSet

> Complementa `viewsets.md`: el ViewSet **siempre** se cablea con un router (no
> `.as_view({...})` a mano). Este doc es la mecánica del router: `register`,
> `basename`, prefijos, y el URL de las `@action`.

## `DefaultRouter` — el router del proyecto

El router genera el URLconf del recurso: enlaza list/create/retrieve/update/
partial_update/destroy a `{prefix}/` y `{prefix}/{lookup}/`, y añade cada
`@action`. Estado del repo (PROVEN 2026-07-18): **10** instancias de
`DefaultRouter`, **0** de `SimpleRouter`. El proyecto usa `DefaultRouter`
uniformemente (añade la vista raíz del API + sufijos de formato sobre lo que da
`SimpleRouter`).

    from rest_framework.routers import DefaultRouter
    router = DefaultRouter()
    router.register(r'accounts', AccountViewSet, basename='account')
    urlpatterns = [path('', include(router.urls))]

`register()` recibe **prefix** + **viewset** (obligatorios) y **basename**
(opcional). El patrón de inclusión del proyecto es `path('', include(router.urls))`
(PROVEN: `voucher/urls.py`, `users/urls.py`, `users/admin_urls.py`).

## `basename` — explícito, siempre

El `basename` es la raíz de los nombres de URL generados (`{basename}-list`,
`{basename}-detail`). El router lo **deriva del atributo `queryset`** del
ViewSet; pero un ViewSet que sólo define `get_queryset()` **no tiene** `queryset`
y el registro **falla**::

    'basename' argument not specified, and could not automatically determine
    the name from the viewset, as it does not have a '.queryset' attribute.

Como el proyecto acota la fila con `get_queryset()` (ver `generic-views.md`),
el `basename` se pasa **explícito en cada `register`**. Estado del repo (PROVEN
2026-07-18): **23** `basename=` — coincide con los 23 `router.register`. No se
depende de la derivación automática.

## Prefijo — sin slash final

El prefijo va **sin** slash final: `r'accounts'`, no `r'accounts/'`. El router
añade el slash según su config `trailing_slash` (default: **con** slash, la
convención de Django). Estado del repo (PROVEN 2026-07-18): **0** usos de
`trailing_slash` — se mantiene el slash final por default en toda la superficie.

## URL de una `@action` — `url_path`

Por default el segmento de URL de una `@action` es el **nombre del método** y el
nombre reverse es `{basename}-{método-con-guiones}`. Para cambiar el segmento sin
tocar el nombre del método se usa `url_path` (y `url_name` para el nombre
reverse)::

    @action(detail=True, methods=['post'], url_path='change-password')
    def set_password(self, request, pk=None):
        ...
    # → ^accounts/{pk}/change-password/$   name: 'account-set-password'

Estado del repo (PROVEN 2026-07-18): **17** `url_path=`, **0** `url_name=`. El
proyecto personaliza el **segmento de URL** cuando el nombre del método no es el
segmento deseado, pero deja que el **nombre reverse** salga del default
(`{basename}-{método}`). Reverse de la acción: `self.reverse_action(...)` (ver
`viewsets.md`).

## Router a medida — no se usa aquí

DRF permite subclasar `SimpleRouter`/`BaseRouter` y redefinir `.routes`
(named-tuples `Route`/`DynamicRoute`) o `get_urls()` para una estructura de URL
propia. Estado del repo (PROVEN 2026-07-18): **0** subclases de router. No hay
necesidad — `DefaultRouter` + `basename` explícito + `url_path` cubre la
superficie. **No introducir un router a medida** sin una necesidad estructural
concreta (encapsular un patrón de URL repetido en ≥3 recursos); la vía default es
más simple y ya es la convención.

## `lookup_field` / converters de path

El campo con que se resuelve el detalle es `pk` por default; se cambia con
`lookup_field` en el ViewSet. Para restringir el patrón del lookup (p. ej. sólo
UUID) se usa `lookup_value_regex` (regex) o `lookup_value_converter` (si el
router se instancia con `use_regex_path=False`). Estado del repo (PROVEN
2026-07-18): **2** archivos con `lookup_field`/`lookup_value_regex` — es la
excepción, no la norma (la mayoría resuelve por `pk`).

## Checklist al registrar un ViewSet

1. `router = DefaultRouter()` (no `SimpleRouter`; no router a medida sin razón).
2. `router.register(r'prefijo', VS, basename='...')` — prefijo **sin** slash
   final, `basename` **explícito** (el ViewSet acota con `get_queryset()`, no
   tiene `queryset`).
3. Incluir con `path('', include(router.urls))`.
4. `@action` que cambia de segmento → `url_path='...'`; el nombre reverse sale
   del default.
5. `lookup_field` sólo si la resolución del detalle no es por `pk`.

## Referencias cruzadas

- `viewsets.md` — el ViewSet que el router cablea; `@action`, `permission_map`,
  `reverse_action`.
- `generic-views.md` — `get_queryset()` (por qué no hay `queryset` → `basename`
  explícito).
- `SKILL.md` Phase 7 — cuándo un recurso es ViewSet vs FBV.
- Código: `addons/voucher/urls.py`, `addons/users/urls.py`,
  `addons/users/admin_urls.py` (patrón `DefaultRouter` + `include`).
```
