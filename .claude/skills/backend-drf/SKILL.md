```yml
name: backend-drf
description: "Skill de tecnología para el backend Django 6 + DRF de e-commerce (submódulo api). Usar cuando se implementen o modifiquen vistas, serializers, permisos, endpoints o su OpenAPI en src/addons/**. Cubre: estilo de vista (FBV vs ViewSet vs CBV), autorización por capacidad (HasCapability + azúcar), drf-spectacular, canon codigo_error, y el gate de no-lazy-imports. Invocar en Phase 7 DESIGN/SPECIFY para el contrato del endpoint, Phase 10 EXECUTE para implementarlo, y Phase 11 TRACK/EVALUATE para verificar autorización y schema."
layer: backend
framework: django-drf
project: e-comerce
stack:
  - Python 3.12+
  - Django 6.0.x
  - djangorestframework 3.16.x
  - djangorestframework-simplejwt 5.5.x
  - drf-spectacular 0.29.x
```

# Backend Django + DRF — SKILL

Guía fase-por-fase para vistas/endpoints del submódulo `api` (`src/addons/**`).
Complementa el cheat-sheet `CLAUDE.md` (que sólo lleva el invariante de
seguridad); el detalle vive aquí, on-demand.

---

## Stage 3: DIAGNOSE — Antes de tocar una vista

- ¿El endpoint es **una acción** (un verbo: login, confirmar 2FA, cambiar pass)
  o un **recurso CRUD** (colección + detalle)? Determina el estilo (abajo).
- ¿Qué **capacidad** lo gobierna? Toda vista con datos/acciones va gateada por
  `HasCapability` (fail-closed). Localizar/definir el code (`dominio.verbo`).
- ¿Es **cuenta propia** (el usuario gestiona SU cuenta)? → capacidad `account.*`
  sembrada en TODOS los roles en `seed_authz`.
- ¿Toca un **modelo** nuevo? → migración + (si hay config) `SystemParameter`
  (nada hardcoded).

## Phase 7: DESIGN/SPECIFY — Elegir el estilo de vista

Decisión ratificada (ejecutor 2026-07-18). Tres casos:

| Estilo | Cuándo | Autorización | Wiring |
|---|---|---|---|
| **FBV** `@api_view` | **acción única** (1 verbo) | `@require_capability('dom.verbo')` | `path()` → función |
| **`ViewSet`/`ModelViewSet`** | **recurso CRUD** (list/retrieve/create/update/destroy + `@action`) | `permission_classes=[IsAuthenticated, HasCapability]` + `permission_map={action: cap}` | **router** (`DefaultRouter().register`) |
| **CBV `APIView`** | legacy / multi-método complejo que no es recurso CRUD | `CapabilityRequiredMixin` + `required_capability` | `path(..., V.as_view())` |

Criterio: un verbo suelto = FBV (evita el boilerplate de una clase por método);
un recurso = ViewSet. No hay clase base de proyecto (no existe `BaseAPIView`) —
lo transversal vive en las permission classes + `codigo_error` + drf-spectacular.

**Reglas duras de ViewSet:**

- ViewSet **SIEMPRE con router**; NUNCA `.as_view({'get':'list'})` manual con
  `@action` — el bind manual salta el router e **ignora las `permission_classes`
  de la acción** (hueco de seguridad, advertencia de DRF). Verificado limpio
  2026-07-18: 43 `router.register`, 0 `.as_view({…})` manual.
- Router prefix **sin** slash final (`r'addresses'`, no `r'addresses/'`).
- Gate por acción: `permission_map={action: cap}` o
  `@action(..., permission_classes=[IsAuthenticated, RequireCapability(cap)])`.

## Phase 10: EXECUTE — Implementar

### Autorización por capacidad (DEC-11) — NUNCA `IsAuthenticated` a secas

`HasCapability` es fail-closed: sin capacidad declarada → 403. Usar `IsAuthenticated`
solo saltaría el modelo de capacidades. Azúcar en `addons.authz.permissions`:

- **FBV:** `@require_capability('dom.verbo')` (fija
  `permission_classes=[IsAuthenticated, RequireCapability(code)]`).
- **ViewSet/CBV:** `permission_classes=[IsAuthenticated, HasCapability]` +
  `permission_map` / `required_capability`, o `CapabilityRequiredMixin`.
- **Capacidad nueva:** añadirla al catálogo de
  `addons/authz/management/commands/seed_authz.py` (`NAMED_ACTIONS` para acciones
  con punto, o `CRUD_NOUNS` para sustantivos graduables). Si NO se añade, el
  sweep de URLconf de `tests/integration/authz/test_capability_sugar.py`
  (`unknown_capability_codes`) **falla**.
- **Cuenta propia:** además, añadir el code a `self_account_codes` de
  `seed_authz` (se siembra en TODOS los roles — DEC-ENF-01) para que ningún
  usuario quede fuera de su propia cuenta.
- **DEC-12 (re-auth):** acciones **sensibles** mutantes exigen sesión elevada
  fresca (`assert_session_fresh`); marcar el code como sensible en el catálogo
  sólo si el flujo de re-auth está cableado en el consumidor.

### FBV — patrón + orden de decoradores

`@extend_schema` arriba, `@api_view`, `@require_capability` **debajo** (más
interno, para que DRF lea `permission_classes` al envolver):

```python
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.decorators import api_view
from rest_framework.response import Response
from addons.authz.permissions import require_capability

@extend_schema(tags=['dom'], summary='...', request=MiSerializer,
               responses={200: OpenApiResponse(description='...'),
                          400: OpenApiResponse(description='CODIGO_ERROR')})
@api_view(['POST'])
@require_capability('dom.verbo')
def mi_accion(request):
    ...
    return Response({'codigo_error': 'X', 'detail': '...'}, status=400)
```

FBV multi-método: `@extend_schema(methods=['GET'], ...)` apilados.

### drf-spectacular en CADA endpoint — no olvidar

`@extend_schema(tags=[...], summary='...', request=<Serializer|None>,
responses={200: ..., 4xx: OpenApiResponse(description='CODIGO_ERROR')})`. Un
endpoint sin `@extend_schema` degrada el OpenAPI publicado. ViewSet:
`@extend_schema_view(list=..., retrieve=...)` o `@extend_schema` por método/acción.

### Canon de errores y estilo

- Clave de error canónica **`codigo_error`** (no `error_code`). El gate
  canon-idioma lo vigila.
- **Zero lazy imports** — imports al top del módulo; el pre-commit
  (`scripts/check_no_lazy_imports.py`) lo bloquea. Excepciones: sólo las 4
  documentadas en `.claude/rules/no-lazy-imports.md`.
- Serializers: `ModelSerializer` hereda los validators del campo del modelo.

## Phase 11: TRACK/EVALUATE — Verificar

- **DB + pytest** contra MariaDB real (nunca SQLite):
  `bash /home/user/e-commerce-db/scripts/start_db.sh` + `uv run pytest <ruta> -q --reuse-db`.
- **Autorización:** un test que confirme 403 sin la capacidad y 200 con ella
  (patrón `seed_authz` + `assign_buyer_role`/`RoleAssignment` +
  `invalidate_capabilities`; ver `tests/integration/authz/test_self_account_caps.py`).
- **Sweep de capacidades:** `test_capability_sugar.py` (`unknown_capability_codes`)
  barre todo el URLconf — cada `required_capability` debe existir en el catálogo.
- **Lazy gate:** `python3 scripts/check_no_lazy_imports.py` (exit 0).
- **Migración nueva:** aplica con `--reuse-db`; verificar `makemigrations
  <app> --check --dry-run` limpio.

## Referencias on-demand (`references/`)

Cargar el doc del eje que se está tocando (no todo el skill):

- [`request-object.md`](references/request-object.md) — leer body/params/usuario
  de la petición (`request.data` vs `request.POST`; `query_params`; `user`/`auth`;
  parse errors 400/415).
- [`response-object.md`](references/response-object.md) — construir la respuesta
  (`Response(data, status)` con primitivos; cuerpo `codigo_error`; headers;
  excepción streaming/`FileResponse`).
- [`views.md`](references/views.md) — mecánica APIView/`@api_view`, policy
  attributes ↔ decoradores, ciclo de dispatch + `handle_exception` central
  (ADR-019), `raise APIException`, y la receta de **throttle en FBV**.
- [`generic-views.md`](references/generic-views.md) — `GenericAPIView` y clases
  concretas (List/Retrieve/Create/…), `get_queryset()` con acotamiento de fila
  por usuario (capa L3), N+1 vía `select_related`/`prefetch_related`, hooks
  `perform_create/update/destroy`, PUT-no-crea (404).
- [`viewsets.md`](references/viewsets.md) — recurso CRUD como
  `ViewSet`/`ModelViewSet` + router, `@action` (detail True/False), gate por
  acción con `permission_map`, introspección `self.action`, base a medida con
  mixins, y la regla dura de nunca `.as_view({...})` manual.
- [`routers.md`](references/routers.md) — cableado con `DefaultRouter`,
  `basename` explícito (el ViewSet acota con `get_queryset()` → sin `queryset`),
  prefijo sin slash final, `url_path` para el URL de una `@action`, y por qué no
  se usa router a medida.
- [`parsers.md`](references/parsers.md) — cómo se puebla `request.data` según
  `Content-Type`; default JSON+form+multipart sin override; cuándo fijar
  `parser_classes = [MultiPartParser, FormParser]` para subidas de archivo/CSV.
- [`renderers.md`](references/renderers.md) — cómo se serializa la respuesta
  según `Accept`; default **JSON-only** en prod (browsable sólo en dev); renderer
  a medida (`BaseRenderer`) para exports CSV/PDF/XLSX (patrón `reports/views.py`).
- [`serializers.md`](references/serializers.md) — `ModelSerializer`/`Serializer`,
  `Meta.fields` explícito (nunca `'__all__'`), validación 3 niveles
  (`validate_<campo>`/`validate`/`is_valid(raise_exception=True)` → 400 sellado),
  contexto vía `save(user=...)` (no `CurrentUserDefault`), nested writable
  explícito.
- [`serializer-fields.md`](references/serializer-fields.md) — campos:
  `SerializerMethodField` (calculado read-only, cuidar N+1), `source=`, dinero con
  `DecimalField(...,decimal_places=2)` (nunca `FloatField`; sale como string),
  `write_only`/`read_only`, `ImageField`/`FileField` + MultiPart; sin campo a
  medida (usar nested/method field).
- [`serializer-relations.md`](references/serializer-relations.md) — relaciones:
  idioma `<campo>_id` write_only (`PrimaryKeyRelatedField` con `queryset=`) +
  nested de lectura, `SlugRelatedField` por campo único, inversas por
  `related_name`, M2M `through` read-only; N+1 se optimiza en la vista, no DRF.
- [`validators.md`](references/validators.md) — validación reutilizable:
  validador **función** en `<app>/validators.py` + `validators=[...]`,
  `UniqueValidator`, `unique_together` auto-generado por `ModelSerializer`; casos
  ambiguos van a `.validate()`/vista, no a `Meta.validators = []`.
- [`authentication.md`](references/authentication.md) — identidad de la petición:
  default = **sesión de servidor** (`CsrfExemptSessionAuthentication`, ADR-018;
  cookie `__Host-`, sin token CSRF), SimpleJWT instalado pero **dormido**;
  contrato **401** (sesión ausente) vs **403** (sin capacidad).
- [`permissions.md`](references/permissions.md) — autorización: nunca
  `IsAuthenticated` a secas → `HasCapability` (DEC-11, motor) + `IsOwnerOrAdmin`
  (object-level); las 3 capas (queryset L3 / capacidad / campos); object-level
  sólo en retrieve/update/destroy (create se restringe en serializer/perform_create).
- [`caching.md`](references/caching.md) — caché de **bajo nivel** `cache.get/set`
  (backend `DatabaseCache`), no `cache_page`; clave `dominio:tema:<inputs>` + TTL
  por vista (patrón `reports/views.py`); `invalidate_capabilities(user.id)` tras
  cambiar rol.
- [`throttling.md`](references/throttling.md) — límite de tasa: default
  anon/user (off en tests), scope por endpoint = **3 piezas**
  (`throttle_classes=[ScopedRateThrottle]` + `throttle_scope` +
  `DEFAULT_THROTTLE_RATES`); gotcha `throttle_scope` huérfano = no-op silencioso
  (H-CICLO26-01); FBV vía `UserRateThrottle` con `scope=`.
- [`filtering.md`](references/filtering.md) — filtrado **manual en
  `get_queryset()`** (`query_params.get`), no `django-filter` (no instalado);
  ordenamiento expuesto = **allowlist** (`CatalogueOrderingFilter`), nunca campo
  libre; `SearchFilter`/`OrderingFilter` de DRF no se usan.
- [`pagination.md`](references/pagination.md) — **sin paginación global** → todo
  list endpoint declara `pagination_class` (subclase `PageNumberPagination` con
  `page_size`/`page_size_query_param`/`max_page_size`); envelope default
  `{count,next,previous,results}` (contrato UI); `APIView` plano pagina a mano.
- [`versioning.md`](references/versioning.md) — versionado de DRF **off**
  (`request.version`=None); se versiona por **prefijo de URL + namespace Django**
  (`api/v1/`=webhooks externos estables, `api/v2/`=API del producto con
  namespaces `<app>_v2`); no ramificar por versión.
- [`content-negotiation.md`](references/content-negotiation.md) —
  `DefaultContentNegotiation` global (trivial: JSON-only en prod; `q` values
  ignorados); único negociador a medida `_PassthroughNegotiator` (exports:
  ignora `?format=`, la vista es dueña del formato).
- [`metadata.md`](references/metadata.md) — metadata de `OPTIONS` **no se usa**
  (`SimpleMetadata` default, 0 overrides); el contrato del API es
  **drf-spectacular** (`DEFAULT_SCHEMA_CLASS=AutoSchema`, `@extend_schema`,
  `/api/schema/` + Swagger/Redoc), no `OPTIONS`.
- [`schema.md`](references/schema.md) — el schema **nativo** de DRF
  (`rest_framework.schemas`/`@schema`) está deprecado y **no se usa** (0); el
  contrato OpenAPI 3 lo genera **drf-spectacular** (`@extend_schema` 354, `tags`
  273, `OpenApiResponse` 135, `OpenApiParameter` 108, `extend_schema_field` 72;
  `@extend_schema_view`/`OpenApiExample` 0) servido en `/api/schema/` + Swagger +
  Redoc; `CONTACT`=operador L0 (Kaupamex).
- [`format-suffixes.md`](references/format-suffixes.md) — sufijos `.json` en URL
  **no se usan** (`format_suffix_patterns` 0, kwarg `format=None` 0); `?format=`
  queda default-habilitado (`URL_FORMAT_OVERRIDE='format'`) pero no-op en prod
  (JSON-only), **salvo** el export view que se apropia de `?format=` como contrato
  y neutraliza a DRF con `_PassthroughNegotiator` (no global).
- [`reverse-urls.md`](references/reverse-urls.md) — el `reverse` de DRF
  (`rest_framework.reverse`) **no se usa** (0); la URL absoluta se arma con
  `request.build_absolute_uri(...)` (13, imágenes/descargas en
  `SerializerMethodField`, fallback relativo si falta `request`); resolver
  `viewname` es `django.urls.reverse` con namespace `_v2`; sin serializers
  hyperlinked.
- [`exceptions.md`](references/exceptions.md) — el contrato de error lleva la
  clave canónica `codigo_error` (390; string INGLÉS) además de `detail`, via
  `ValidationError` (182) o 13 `APIException` codificadas
  (`<app>/exceptions.py`, p.ej. `ReauthRequired` DEC-12); el `EXCEPTION_HANDLER`
  central (`core.exception_handling`, ADR-019) **no cambia el cuerpo** — solo
  sella el error en `RequestLog` (no bloqueante, DEC-LOG-04); sin
  `drf-standardized-errors` ni `handler500/400`.
- [`status-codes.md`](references/status-codes.md) — estado real: el número pelado
  `status=NNN` **domina** (255) sobre la constante `status.HTTP_*` (89) — drift
  BAJA vs la recomendación de DRF; código **nuevo** usa la constante, no se migra
  en masa. El `status_code` de clase en `APIException` (13) sí es idioma DRF (no
  cambiar). Helpers `is_success()`/etc en 0. El código correcto sale del contrato
  (401/403, 404 por row-scoping, 409/422, 429).

## Referencias de código

- `addons/authz/permissions.py` — `HasCapability`, `RequireCapability`,
  `CapabilityRequiredMixin`, `require_capability`, `IsOwnerOrAdmin`.
- `addons/authz/management/commands/seed_authz.py` — catálogo de capacidades.
- `.claude/rules/no-lazy-imports.md` — gate de imports.
- DRF docs: Views (APIView/FBV) · ViewSets (router + `@action`) · Requests.
- Precedente FBV: `addons/authz_totp/` (2FA, migrado a FBV 2026-07-18).
```
