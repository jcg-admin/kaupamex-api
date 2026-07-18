```yml
type: Reference (lazy-load on-demand)
applies_when: El schema sale vacío/roto, hay warnings, la UI Swagger/Redoc está en blanco, o @extend_schema "no hace nada"
created_at: 2026-07-18 03:49:53
status: Aprobado
version: 1.0.0
source: drf-spectacular FAQ
```

# FAQ / troubleshooting — síntomas mapeados al proyecto

> Índice de síntomas del FAQ oficial con el diagnóstico **para este proyecto**:
> qué ya está resuelto, qué no aplica (y por qué), y qué usar si aparece.

## Ya resuelto en el proyecto (no re-investigar)

- **"Schema vacío / faltan endpoints" (versioning):** NO muerde aquí. El versionado
  de DRF está **off** (`DEFAULT_VERSIONING_CLASS=None`, ver
  `backend-drf/references/versioning.md`), así que **todos** los endpoints son
  "unversioned" para DRF y **aparecen** en el schema. El prefijo `v1`/`v2` es
  Django, no DRF — no hace falta `--api-version`.
- **"Operaciones duplicadas con sufijo `{format}`":** ya excluidas — el preprocessing
  hook `preprocess_exclude_path_format` está wired (`base.py:415`). Coherente con no
  usar format-suffixes (`backend-drf/references/format-suffixes.md`).
- **"Mis extensiones no se detectan / ¿dónde las pongo?":** en el `schema.py` de la
  app, registradas por el PREPROCESSING hook `register_app_schema_extensions`.
  **El FAQ recomienda `apps.ready()` — aquí NO se usa** (lo bloquea
  `check_no_lazy_imports`; ver `customization.md`/`spectacular-settings.md`). Es la
  desviación deliberada del proyecto.
- **"Warnings de Enum / sufijo raro":** el postprocessing hook de enums nombra los
  choice sets y avisa de colisiones → se resuelven en `ENUM_NAME_OVERRIDES`
  (referencia `enum-overrides`, por pieza).

## Gotchas que SÍ aplican (el proyecto tiene mucho `APIView`/FBV)

- **"`@extend_schema` en `APIView` no hace efecto":** hay que ponerlo en el
  **método de entrada** — `get`/`post`, no en `list`/`retrieve` (esos son de
  ViewSet). Cuidado con `ListAPIView`: su entrypoint real es `get`, no `list`. Como
  el proyecto es mayormente FBV/`APIView` (ver `backend-drf/references/views.md`),
  este es el error más probable al anotar.
- **`@api_view` — anotar el decorador:** un método → `@extend_schema` directo sobre
  la función. **Varios métodos** (`@api_view(['GET','POST'])`) → es el **único** caso
  donde el proyecto usaría `@extend_schema_view` (hoy 0; ver `customization.md`).
- **`@action` con `responses=...(many=True)` mal paginado / con filtros:** la acción
  hereda `pagination_class`/`filter_backends` del ViewSet. Limpiarlos **en el
  `@action`**: `pagination_class=None` (y `filter_backends=[]` si aplica). Hoy 0
  usos — aplicar si aparece.
- **`@action(detail=False)` no devuelve lista:** `detail` solo define el ruteo
  (`x/action` vs `x/{id}/action`), no la forma de la respuesta. Para una lista:
  `@extend_schema(responses=XSerializer(many=True))`.

## Swagger/Redoc en blanco (CSP) — no aplica en Django, caveat en prod

**No aplica** en la capa Django: `django-csp` **no está instalado** (PROVEN
2026-07-18, 0 en `pyproject.toml`/settings). Las UIs cargan sus assets del **CDN**
(`SWAGGER_UI_DIST` default jsdelivr). **Caveat de producción:** si se añade una CSP
(p.ej. en el vhost Apache del submódulo `server`), los assets del CDN se bloquean y
la UI queda en blanco → o servir con **sidecar** (`SWAGGER_UI_DIST: 'SIDECAR'`) o
permitir `cdn.jsdelivr.net` en `CSP_DEFAULT_SRC`. Diagnóstico: consola del navegador
→ errores `Content Security Policy`.

## Mecanismos disponibles pero NO usados (0 PROVEN — usar solo si el síntoma aparece)

| Síntoma | Mecanismo | Uso hoy |
|---|---|---|
| serializer distinto según situación | `PolymorphicProxySerializer` | 0 |
| respuesta envuelta (envelope) | helper `enveloper` + `@extend_schema_serializer` | 0 (no hay envelope; el contrato es plano + `codigo_error`) |
| `ViewSet.list` devuelve **un** objeto | `forced_singular_serializer` | 0 (anti-patrón; usar `APIView`) |
| serializer **recursivo** | `lazy_serializer` | 0 |
| varios `SpectacularAPIView` con settings distintos | `custom_settings` | 0 (un solo schema) |
| `get_queryset` depende de `request` en gen-time | fallback `swagger_fake_view` → `Model.objects.none()` | 0 (ninguno lo necesita hoy) |

Si uno de estos se necesita, seguir el patrón del FAQ **dentro** del `schema.py` de
la app o el `@extend_schema` del método — nunca tocando `base.py`.

## Binarios / archivos en memoria

El FAQ propone `responses=bytes` + un `BaseRenderer` binario. El proyecto ya sirve
export binario (CSV/PDF/XLSX) con **renderers propios** en `reports`
(`responses=bytes` = 0; usa el dict de `responses` por media type). Ver
`backend-drf/references/renderers.md` y `content-negotiation.md`. Para un `FileField`
de request, el `COMPONENT_SPLIT_REQUEST=True` ya modela bien la dualidad
request/response (ver `client-generation.md`); además fijar
`parser_classes=[MultiPartParser]` en esa vista (ver `backend-drf/references/parsers.md`).

## i18n del schema — disponible, no usado

`USE_I18N=True` (PROVEN `base.py:197`), así que el schema/UI aceptarían `?lang=` y
`--lang`. Hoy no se traduce el schema (summaries en español directo). No introducir
`gettext_lazy` en los `@extend_schema` sin una decisión de producto de API
multi-idioma.

## Referencias cruzadas

- `customization.md` — los 7 pasos (el FAQ remite a ellos para casi todo).
- `spectacular-settings.md` — hooks (`preprocess_exclude_path_format`,
  `register_app_schema_extensions`) y por qué no `ready()`.
- `enum-overrides` (por pieza) — el detalle de `ENUM_NAME_OVERRIDES`.
- `backend-drf/references/views.md` — `APIView`/FBV (el gotcha de `get`/`post`).
- `backend-drf/references/renderers.md` / `versioning.md` / `parsers.md` — export
  binario, versionado off, parser de archivos.
```
