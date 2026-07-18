```yml
type: Reference (lazy-load on-demand)
applies_when: Se lee el cuerpo/params/usuario de una petición en una vista DRF (FBV o CBV)
created_at: 2026-07-18 02:39:06
status: Aprobado
version: 1.0.0
source: DRF api-guide/requests
```

# DRF `Request` — lectura de la petición

> Cargar cuando una vista lee el body, los query params, el usuario o el token
> de la petición. El `Request` de DRF **extiende** `HttpRequest` (por
> composición, no herencia) y añade parsing flexible + autenticación por
> petición.

## Regla principal — `request.data`, nunca `request.POST`

> "If you're doing REST-based web service stuff … you should ignore
> `request.POST`." — Malcolm Tredinnick (Django developers)

- **`request.data`** — contenido **parseado** del body. A diferencia de
  `request.POST`/`request.FILES`:
  - incluye inputs de archivo **y** no-archivo;
  - soporta **PUT/PATCH** (no sólo POST);
  - soporta JSON y otros media types (no sólo form-data).
  - Los serializers se alimentan de aquí: `MiSerializer(data=request.data)`.
- **NUNCA** `request.POST` / `request.FILES` en endpoints REST. Estado del repo
  (PROVEN 2026-07-18): **29** archivos usan `request.data`, **0** usan
  `request.POST`. Mantenerlo en 0.

## `request.query_params`, no `request.GET`

- **`request.query_params`** es el sinónimo correcto de `request.GET`.
  Preferirlo: **cualquier** método HTTP puede llevar query params, no sólo GET.
- Estado del repo (PROVEN 2026-07-18): **24** archivos con `request.query_params`
  vs **1** con `request.GET` — al tocar ese archivo, migrarlo.

## `request.user` / `request.auth` — autenticación por petición

- **`request.user`** — usuario autenticado; aquí es `IdentityUser`
  (`USERNAME_FIELD='email'`). Si la petición no está autenticada →
  `AnonymousUser`. Es lo que consulta `HasCapability` / `@require_capability`
  para resolver capacidades.
- **`request.auth`** — contexto extra de auth; con simplejwt es el token
  validado. `None` si no autenticado o sin contexto.
- `WrappedAttributeError` al acceder `.user`/`.auth` = un authenticator lanzó un
  `AttributeError` interno; el bug está en el authenticator, no en la vista.

## Errores de parsing — manejados por DRF (no reinventar)

- Body **malformado** → `ParseError` → **400** (automático en `APIView` /
  `@api_view`). No envolver en try/except para devolver 400 manual.
- Content-type **no parseable** → `UnsupportedMediaType` → **415** (automático).
- Estos códigos ya salen bien por el framework; el handler sólo valida la
  semántica (con el serializer) y devuelve `codigo_error` de negocio en 4xx.

## Otros atributos (rara vez necesarios)

- **`request.method`** — método HTTP en mayúsculas (soporta PUT/PATCH/DELETE por
  formulario del browsable API).
- **`request.content_type`** — media type del body; preferirlo sobre
  `request.META.get('HTTP_CONTENT_TYPE')`.
- **`request.stream`** — stream crudo del body (normalmente no se toca; usar
  `request.data`).
- **Content negotiation:** `request.accepted_renderer` /
  `request.accepted_media_type` (para servir distintos formatos por media type).
- **Estándar de Django** disponible igual: `request.META`, `request.session`.

## Checklist al leer una petición

1. Body → `request.data` (no `request.POST`). Alimentar el serializer con él.
2. Query string → `request.query_params` (no `request.GET`).
3. Usuario → `request.user` (ya autenticado por simplejwt; la capacidad la
   resuelve `HasCapability`). No re-implementar auth en la vista.
4. No capturar `ParseError`/`UnsupportedMediaType` para forzar 400/415 — DRF ya
   los mapea; el 4xx de negocio va con `codigo_error`.
