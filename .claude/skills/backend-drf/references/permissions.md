```yml
type: Reference (lazy-load on-demand)
applies_when: Se decide quién puede acceder a un endpoint u objeto — autorización (HasCapability, IsOwnerOrAdmin, object-level)
created_at: 2026-07-18 03:06:09
status: Aprobado
version: 1.0.0
source: DRF api-guide/permissions
```

# DRF Permissions — autorización de la petición

> La autorización **decide** si la petición procede; la autenticación sólo
> identifica (ver `authentication.md`). Corre al inicio de la vista, antes del
> cuerpo. En este proyecto el motor es `HasCapability` (DEC-11) — **este doc es su
> mecánica DRF**; el catálogo de capacidades y el estilo por vista están en
> `SKILL.md` Phase 10.

## Default + regla del proyecto — nunca `IsAuthenticated` a secas

`DEFAULT_PERMISSION_CLASSES` = `IsAuthenticated` (piso global,
`config/settings/base.py:263-265`). Pero `IsAuthenticated` **solo** deja pasar a
**cualquier** usuario autenticado — es fail-open respecto al modelo de
capacidades. La regla del proyecto: toda vista con datos/acciones va gateada por
**`HasCapability`** (fail-closed: sin capacidad declarada → 403). Ver el
invariante en `CLAUDE.md` y `SKILL.md`.

> **Deuda conocida (PROVEN 2026-07-18):** hay **27** `permission_classes =
> [IsAuthenticated]` a secas en 7 archivos (`orders`, `cart`, `payments`,
> `catalogue`, `authz`, `session_views`, `search_history`). Parte son endpoints
> self-scoped por `get_queryset(user=...)` (aceptable), parte es drift que la
> iniciativa **`migrar-authz-a-niveles-dec-11`** está cerrando. No añadir nuevos:
> el sweep de `test_capability_sugar.py` y la revisión de esa iniciativa los
> vigilan.

## Los dos permission classes del proyecto

Definidos en `addons/authz/permissions.py` (PROVEN 2026-07-18: **2** clases):

- **`HasCapability(BasePermission)`** — `has_permission`: resuelve la capacidad
  DEC-11 del `request.user` y, para métodos mutantes, aplica el gate de re-auth
  DEC-12 (`assert_session_fresh`). `message` propio → el 403 lleva texto claro.
  Es el **motor**; la azúcar (`RequireCapability`, `CapabilityRequiredMixin`,
  `@require_capability`, `permission_map`) sólo evita repetir `permission_classes`
  — el chequeo real siempre lo hace `HasCapability`.
- **`IsOwnerOrAdmin(BasePermission)`** — `has_object_permission`: **segunda línea**
  sobre el `filter(user=request.user)` del queryset (cierra H-API-PERM-05).
  Permite si el objeto es del usuario, o si es admin con la
  `view.admin_capability`. **No** aplica a POS (una venta no "pertenece" al
  cajero → `HasCapability` con `pos.*`).

## Object-level — cómo y cuándo corre

`has_object_permission` **sólo** corre (a) tras pasar `has_permission` de la
vista, y (b) cuando la vista llama `check_object_permissions(request, obj)`. Las
**genéricas lo llaman solo** en `get_object()` (retrieve/update/destroy); una FBV
o un `get_object` sobrescrito debe llamarlo **explícito**. PROVEN 2026-07-18:
**1** `has_object_permission` (`IsOwnerOrAdmin`), **0** llamadas manuales a
`check_object_permissions` — la protección de fila se apoya sobre todo en el
**row-scoping del queryset** (`get_queryset(user=...)`, ver `generic-views.md`),
con `IsOwnerOrAdmin` como refuerzo donde la vista lo declara.

**Caveats de DRF:**

- **List no aplica object-level** por performance → filtrar el queryset (el
  row-scoping ya lo hace).
- **Create no llama `get_object`** → no hay object-level en `create`; para
  restringir la creación, validarlo en el **serializer** o en `perform_create`.

## Las tres capas de restricción de acceso (síntesis del proyecto)

DRF ofrece tres mecanismos; el proyecto los usa así:

| Capa DRF | Mecanismo del proyecto | Doc |
|---|---|---|
| `queryset`/`get_queryset()` | **row-scoping L3** `filter(user=...)` — qué filas se ven/mutan | `generic-views.md` |
| `permission_classes` | **capacidad DEC-11** (`HasCapability`) — qué verbos | este doc + `SKILL.md` |
| `serializer_class` | campos `read_only`/`write_only` — qué campos | `serializer-fields.md` |

Las tres se componen: el queryset limita filas, `HasCapability` el verbo, el
serializer los campos. (Object-level permission sólo aplica a retrieve/update/
destroy; list/create se protegen por queryset/serializer.)

## Permission a medida — subclasear `BasePermission`

`has_permission(self, request, view)` (vista) y/o `has_object_permission(self,
request, view, obj)` (objeto), devolviendo `True`/`False`. `SAFE_METHODS`
(`GET`/`HEAD`/`OPTIONS`) para distinguir lectura de escritura. `message`/`code`
propios personalizan el `PermissionDenied`. Es el patrón de las 2 clases del
proyecto — cualquier permission nuevo sigue este molde (no una dep de terceros).

## Qué NO se usa

- **Composición bitwise** (`|`/`&`/`~`) de permission classes: DRF la soporta;
  PROVEN 2026-07-18: **0** usos — la lógica por acción va por `permission_map`, no
  por operadores.
- **`DjangoModelPermissions`/`DjangoObjectPermissions`/`IsAdminUser`**: no se usan
  (`IsAdminUser` sólo aparece en un docstring que explica qué reemplazó
  `HasCapability`). El modelo Django de permisos por modelo/`is_staff` fue
  **reemplazado** por capacidades DEC-11.
- **Terceros** (`drf-access-policy`, `django-guardian`, DRF-API-Key, roles pkgs):
  no se usan. El motor de capacidades + record rules L3 cubre el proyecto.

## Checklist al autorizar un endpoint

1. **Nunca** `permission_classes = [IsAuthenticated]` solo → `HasCapability` +
   `permission_map`/`required_capability` (o `@require_capability` en FBV).
2. Capacidad nueva → añadirla a `seed_authz.py` (o el sweep falla; ver `SKILL.md`).
3. ¿Objeto propio del comprador? → row-scoping en `get_queryset(user=...)` +
   `IsOwnerOrAdmin` (declarar `admin_capability` para el bypass admin).
4. ¿FBV con object-level? → llamar `check_object_permissions(request, obj)`
   explícito (las genéricas lo hacen solas).
5. ¿Restringir creación? → en el serializer o `perform_create`, no en
   object-level (no corre en create).
6. 401 (sin sesión) vs 403 (sin capacidad): ver `authentication.md`.

## Referencias cruzadas

- `SKILL.md` Phase 10 — catálogo de capacidades, azúcar, DEC-11/DEC-12, sweep.
- `authentication.md` — 401 vs 403; la auth precede al permiso.
- `generic-views.md` — row-scoping L3 (`get_queryset`) como 1ª capa.
- `serializer-fields.md` — restricción a nivel campo (3ª capa).
- Código: `addons/authz/permissions.py` (`HasCapability`, `IsOwnerOrAdmin`,
  `CapabilityRequiredMixin`, `RequireCapability`, `require_capability`),
  `addons/authz/management/commands/seed_authz.py` (catálogo).
```
