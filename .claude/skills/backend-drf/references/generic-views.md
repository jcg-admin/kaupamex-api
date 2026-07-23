```yml
type: Reference (lazy-load on-demand)
applies_when: Se implementa un recurso CRUD con GenericAPIView o una clase genérica concreta (ListAPIView, RetrieveUpdateDestroyAPIView, …)
created_at: 2026-07-18 02:49:13
status: Aprobado
version: 1.0.0
source: DRF api-guide/generic-views
```

# DRF Generic views — GenericAPIView y clases concretas

> La **decisión de estilo** (FBV vs ViewSet vs CBV) vive en `SKILL.md`
> (Phase 7). Este doc es la **mecánica de las genéricas**: cuándo una clase
> concreta ahorra boilerplate, cómo se acota el queryset por usuario, y cómo
> se evita el N+1 antes de que llegue a producción.

## Cuándo una genérica concreta

`GenericAPIView` extiende `APIView` añadiendo el comportamiento CRUD común
(resolución del queryset, del serializer y del objeto de detalle). Las clases
**concretas** lo combinan con los mixins para cubrir cada operación sin escribir
el handler:

| Clase concreta | Verbos | Uso |
|---|---|---|
| `ListAPIView` | GET (colección) | listar |
| `RetrieveAPIView` | GET (detalle) | obtener uno |
| `CreateAPIView` | POST | crear |
| `ListCreateAPIView` | GET + POST | colección + alta |
| `RetrieveUpdateDestroyAPIView` | GET + PUT/PATCH + DELETE | detalle completo |

Estado del repo (PROVEN 2026-07-18, `class \w+(...)APIView` en `src/addons`):
**6** `ListAPIView`, **1** `RetrieveAPIView`, **1** `CreateAPIView`. El resto de
los recursos CRUD usa `ViewSet` + router (ver `SKILL.md` Phase 7). Criterio:
una genérica concreta encaja cuando el recurso expone **una** operación
estándar; un recurso con el CRUD completo se modela con `ModelViewSet`.

## Atributos que gobiernan una genérica

- **`queryset`** / **`get_queryset()`** — el conjunto base. Definir el **método**,
  no el atributo de clase, cuando la respuesta depende de la petición
  (usuario, `query_params`, Company). El atributo de clase se evalúa una vez al
  importar el módulo; el método se evalúa por petición.
- **`serializer_class`** / **`get_serializer_class()`** — el serializer. El método
  se sobrescribe para servir un serializer de lectura y otro de escritura, o uno
  distinto por rol. Estado del repo: **2** overrides de `get_serializer_class`
  (PROVEN 2026-07-18).
- **`lookup_field`** — el campo con que se resuelve el detalle (default `pk`).
- **`pagination_class`** / **`filter_backends`** — paginación y filtrado; los
  defaults salen de `settings.REST_FRAMEWORK`.

## `get_queryset()` acota la fila por usuario (capa L3)

El método `get_queryset()` es donde se **acota la fila** que cada usuario puede
ver. La autorización tiene dos niveles complementarios: `HasCapability` decide si
el usuario tiene la **capacidad** (verbo permitido); `get_queryset()` filtra a
las **filas propias** (el equivalente en consulta de `IsOwnerOrAdmin` / las
record rules L3).

Estado del repo — **11** archivos definen `get_queryset` (PROVEN 2026-07-18).
Ejemplo del patrón de acotamiento::

    # src/addons/users/views.py:261 (PROVEN)
    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

Un usuario autenticado con la capacidad de listar direcciones sólo obtiene **las
suyas** — la capacidad no basta, la fila también se restringe. Sin este filtro,
la capacidad expondría las filas de todos los usuarios.

## Evitar el N+1 — `select_related` y `prefetch_related`

`get_queryset()` es también donde se resuelve el **N+1** antes de que el
serializer dispare una consulta por cada objeto anidado:

- **`select_related('fk', 'o2o')`** — para ForeignKey y OneToOne. Hace un JOIN;
  trae la relación en la misma consulta.
- **`prefetch_related('reverse', 'm2m')`** — para relaciones inversas y
  ManyToMany. Hace una segunda consulta y une en Python.

Estado del repo (PROVEN 2026-07-18): **113** usos de `select_related` y **51** de
`prefetch_related` en `src/addons/**`. Es el patrón establecido; una genérica que
serializa objetos con relaciones **anota el queryset** en `get_queryset()`, no
deja que el serializer las resuelva una por una::

    def get_queryset(self):
        return (Order.objects
                .filter(user=self.request.user)
                .select_related('shipping_address')      # FK → JOIN
                .prefetch_related('items__product'))     # reverse+FK → 1 consulta extra

## Hooks de guardado — `perform_create` / `perform_update` / `perform_destroy`

Los mixins de escritura delegan el guardado en un hook sobrescribible, para
inyectar contexto o disparar efectos sin reescribir el handler completo. Estado
del repo: **17** hooks `perform_*` (PROVEN 2026-07-18).

- **Inyectar el usuario en el alta** (no se confía en el body)::

      def perform_create(self, serializer):
          serializer.save(user=self.request.user)

- **Efecto posterior al guardado** (notificar, encolar tarea) tras
  `serializer.save()`.
- **Validación que sólo se conoce con la petición**: sube un `ValidationError`
  desde el hook — el handler central de excepciones lo sella con `codigo_error`
  (ver `views.md`). No construir el 4xx manualmente.

## PUT no crea — 404 por defecto (DRF 3.x)

Un `PUT` a un detalle inexistente **no crea** el objeto: devuelve **404**. El
comportamiento *PUT-as-create* de versiones antiguas se retiró. Si un flujo
necesita "crear o actualizar", se modela explícito (endpoint de alta separado o
lógica en el hook), no se apoya en el `PUT`.

## No hay clase base de proyecto

No existe un `BaseAPIView` propio. Lo transversal (forma del error
`codigo_error`, autorización por capacidad, schema `drf-spectacular`) vive en las
permission classes, el handler central de excepciones y los decoradores — no en
una jerarquía de vistas. Una genérica del proyecto hereda directo de la clase
concreta de DRF y aporta su `get_queryset` / `serializer_class` / gate de
capacidad.

## drf-spectacular en la genérica

`@extend_schema` (o `@extend_schema_view(list=..., retrieve=...)` para anotar por
operación) sobre la clase. Sin anotación, el OpenAPI publicado se degrada — igual
que en cualquier otra vista (ver `SKILL.md` Phase 10 y `views.md`).

## Checklist al implementar una genérica

1. ¿Una sola operación estándar? → clase concreta. ¿CRUD completo? → `ViewSet`
   (ver `SKILL.md`).
2. `get_queryset()` (método, no atributo) con el filtro de fila por usuario/Company.
3. `select_related` (FK/O2O) + `prefetch_related` (inverso/M2M) para las
   relaciones que el serializer recorre.
4. Autorización por capacidad (`HasCapability` + `permission_map` / mixin) — nunca
   `IsAuthenticated` a secas.
5. Contexto de escritura vía `perform_create/update/destroy`, no en el handler.
6. `@extend_schema` en la clase.

## Referencias cruzadas

- `views.md` — `APIView`, ciclo de dispatch, handler central de excepciones.
- `request-object.md` / `response-object.md` — lectura y construcción de la
  petición/respuesta.
- `SKILL.md` Phase 7 — decisión FBV / ViewSet / CBV; Phase 10 — autorización.
- Código: `src/addons/users/views.py` (`get_queryset` con filtro por usuario),
  `addons/authz/permissions.py` (`HasCapability`, `IsOwnerOrAdmin`).
```
