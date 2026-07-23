```yml
type: Reference (lazy-load on-demand)
applies_when: Se implementa un recurso CRUD como ViewSet/ModelViewSet + router, o se añade una @action a un ViewSet existente
created_at: 2026-07-18 02:51:16
status: Aprobado
version: 1.0.0
source: DRF api-guide/viewsets
```

# DRF ViewSets — recurso CRUD + router + `@action`

> La **decisión de estilo** (FBV vs ViewSet vs CBV) vive en `SKILL.md`
> (Phase 7): un verbo suelto = FBV; un **recurso** = ViewSet. Este doc es la
> mecánica del ViewSet: acciones, router, `@action`, e introspección por acción.

## Qué es un ViewSet

Un `ViewSet` es una clase-vista que **no** expone handlers `.get()`/`.post()`,
sino **acciones**: `.list()`, `.retrieve()`, `.create()`, `.update()`,
`.partial_update()`, `.destroy()`. Los handlers se enlazan a las acciones al
finalizar la vista con `.as_view()` — y ese enlace lo hace el **router**, no el
código a mano.

Ventaja: la lógica repetida (queryset, serializer) se declara **una vez**;
el URLconf lo genera el router. Trade-off: menos control explícito que un
URLconf a mano — se acepta para imponer una configuración de URL consistente en
un API grande.

## Jerarquía — cuál base elegir

| Base | Provee | Uso |
|---|---|---|
| `ViewSet` | nada (defines cada acción) | recurso con lógica no estándar |
| `GenericViewSet` | `get_object`/`get_queryset` + mixins que tú añades | base a medida (subset de acciones) |
| `ModelViewSet` | list/retrieve/create/update/partial_update/destroy | CRUD completo de un modelo |
| `ReadOnlyModelViewSet` | list + retrieve | recurso de sólo lectura |

Estado del repo (PROVEN 2026-07-18, `class \w+(...)` en `src/addons`): **14**
`ModelViewSet`, **2** `ReadOnlyModelViewSet`, **18** `ViewSet` plano. El
`ViewSet` plano es frecuente aquí porque la acción define su propia lógica
(servicio de dominio) en vez de mapear 1:1 a un `queryset`.

`ModelViewSet` normalmente exige `queryset` + `serializer_class`::

    class AccountViewSet(viewsets.ModelViewSet):
        queryset = Account.objects.all()
        serializer_class = AccountSerializer
        permission_classes = [IsAuthenticated, HasCapability]
        permission_map = {'list': 'account.view', 'create': 'account.create', ...}

Para acotar por usuario/Company, sobrescribir `get_queryset()` (ver
`generic-views.md`). **Al quitar el atributo `queryset`**, el router ya no puede
derivar el `basename` — hay que pasarlo explícito en `router.register(...,
basename='...')`.

## Router — SIEMPRE, nunca `.as_view({...})` manual

El ViewSet se registra con `DefaultRouter`; el URLconf se genera solo::

    from rest_framework.routers import DefaultRouter
    router = DefaultRouter()
    router.register(r'accounts', AccountViewSet, basename='account')
    urlpatterns = router.urls

Estado del repo (PROVEN 2026-07-18): **23** `router.register`, **0**
`.as_view({...})` manual.

**Reglas duras:**

- **NUNCA** `AccountViewSet.as_view({'get': 'list'})` a mano cuando el ViewSet
  tiene `@action`. El bind manual **salta el router e ignora ajustes de la
  acción como `permission_classes`** (hueco de seguridad; advertencia explícita
  de DRF). Con router, cada acción conserva su gate.
- Prefijo del router **sin** slash final: `r'accounts'`, no `r'accounts/'` — el
  router añade el slash según su configuración (a diferencia de un patrón Django
  estándar).

## `@action` — rutas extra sobre el recurso

Los métodos ad-hoc que deben ser ruteables se marcan con `@action`. `detail=True`
→ opera sobre un objeto (la URL lleva `pk`); `detail=False` → sobre la colección.

Estado del repo (PROVEN 2026-07-18): **34** `@action` (**24** `detail=True`,
**6** `detail=False`; el resto sin kwarg explícito = `detail=False` por default).

`@action` rutea `GET` por defecto; otros métodos vía `methods=[...]`. **Overridea
config de nivel-ViewSet** — incluido `permission_classes`, que es como se gatea
la acción por capacidad en este proyecto::

    from addons.authz.permissions import RequireCapability

    @action(detail=True, methods=['post'],
            permission_classes=[IsAuthenticated, RequireCapability('account.security')])
    def set_password(self, request, pk=None):
        user = self.get_object()
        ...

- `url_path` / `url_name` cambian el segmento de URL y el nombre reverse.
- Mapear métodos HTTP adicionales a métodos distintos: `@action(methods=['put'])`
  + `@nombre.mapping.delete`.
- Reverse de la URL de una acción: `self.reverse_action('set-password', args=[pk])`.

## Autorización por acción — `permission_map` (azúcar del proyecto)

En vez de sobrescribir `get_permissions()` acción por acción, el proyecto usa el
atributo **`permission_map`** (mapea `acción → code de capacidad`) junto a
`permission_classes = [IsAuthenticated, HasCapability]`. Estado del repo (PROVEN
2026-07-18): **30** `permission_map` vs sólo **2** overrides de
`get_permissions`. El `permission_map` es la vía preferida; el override manual de
`get_permissions` queda para casos que no encajan en el mapa (p. ej. permiso
distinto por acción que no es capacidad).

Cualquier code usado en `permission_map` o en `RequireCapability(code)` de una
`@action` debe existir en el catálogo de `seed_authz.py`, o el sweep de URLconf
de `test_capability_sugar.py` (`unknown_capability_codes`) **falla** (ver
`SKILL.md` Phase 10).

## Introspección — `self.action`

Durante el dispatch, el ViewSet expone `self.action` (`'list'`, `'create'`, …),
`self.detail`, `self.basename`, `self.name`, `self.suffix`. Se inspeccionan para
ajustar comportamiento por acción (queryset o serializer distinto en `list` vs
`retrieve`). Estado del repo (PROVEN 2026-07-18): **7** usos de `self.action`.

**Gotcha:** `self.action` **no** está disponible en `get_parsers`,
`get_authenticators` ni `get_content_negotiator` — se fija *después* de que el
framework los llama; accederlo ahí lanza `AttributeError`.

## Base a medida — subset de acciones

Para un recurso que no necesita el CRUD completo, se compone
`GenericViewSet` + los mixins requeridos, en vez de `ModelViewSet` + restringir
por permisos::

    from rest_framework import mixins, viewsets

    class CreateListRetrieveViewSet(mixins.CreateModelMixin,
                                    mixins.ListModelMixin,
                                    mixins.RetrieveModelMixin,
                                    viewsets.GenericViewSet):
        pass   # override queryset + serializer_class en la subclase

Restringir un `ModelViewSet` "por permisos" a menos acciones deja rutas vivas que
devuelven 403; componer el mixin exacto **no genera** la ruta. Preferir componer
el subset cuando el recurso es estable en su forma.

## Checklist al implementar un ViewSet

1. ¿CRUD completo de un modelo? → `ModelViewSet`. ¿Sólo lectura? →
   `ReadOnlyModelViewSet`. ¿Subset? → `GenericViewSet` + mixins. ¿Lógica de
   dominio no-CRUD? → `ViewSet` plano.
2. Registrar con `DefaultRouter().register(r'prefijo', VS, basename=...)` — sin
   slash final; `basename` explícito si se quitó `queryset`.
3. `permission_classes = [IsAuthenticated, HasCapability]` + `permission_map`
   (nunca `IsAuthenticated` a secas).
4. `@action` con su propio `permission_classes=[..., RequireCapability(code)]`;
   `code` sembrado en `seed_authz.py`.
5. `get_queryset()` acota fila por usuario/Company + `select_related`/
   `prefetch_related` (ver `generic-views.md`).
6. `@extend_schema_view(list=..., retrieve=...)` o `@extend_schema` por
   acción/método (drf-spectacular).
7. Nunca `.as_view({...})` a mano con `@action`.

## Referencias cruzadas

- `generic-views.md` — `GenericAPIView`, `get_queryset` (row-scoping L3), N+1.
- `views.md` — `ViewSet` hereda de `APIView`: ciclo de dispatch, handler central.
- `SKILL.md` Phase 7 — decisión FBV / ViewSet / CBV; Phase 10 — autorización +
  el sweep de capacidades.
- Código: `addons/authz/permissions.py` (`HasCapability`, `RequireCapability`),
  `addons/authz/management/commands/seed_authz.py` (catálogo).
```
