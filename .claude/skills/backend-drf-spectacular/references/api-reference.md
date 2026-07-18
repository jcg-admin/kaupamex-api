```yml
type: Reference (lazy-load on-demand)
applies_when: Se busca qué utilidad/clase de drf-spectacular existe para un caso, o su firma
created_at: 2026-07-18 03:55:33
status: Aprobado
version: 2.0.0
source: drf-spectacular API Reference (utils/types/views/extensions/hooks/openapi/contrib)
```

# API Reference — catálogo del API público de drf-spectacular

> Catálogo completo de la superficie pública de drf-spectacular: cada símbolo,
> qué es y cuándo se ocupa. Referencia neutra — el detalle de los patrones
> aplicados vive en `customization.md`/`spectacular-settings.md`; aquí el mapa
> del API para elegir la herramienta correcta.

## `drf_spectacular.utils`

| Símbolo | Qué es | Cuándo ocuparlo |
|---|---|---|
| `extend_schema` | decorador principal de operación | siempre, por método (ver args abajo) |
| `extend_schema_field` | tipar un field/`SerializerMethodField` | `SerializerMethodField` sin tipo inferible |
| `extend_schema_serializer` | override de serializer (`exclude_fields`, `deprecate_fields`, `component_name`, `many`, `examples`) | ocultar/deprecar un campo, forzar `many=False` (envelope), fijar nombre de componente |
| `extend_schema_view` | anotar métodos heredados (`list`/`retrieve`/…) o `@action` desde la clase | ViewSet cuyos métodos no se sobrescriben, o `@api_view` multi-método |
| `inline_serializer` | serializer one-off para request/response | forma a medida sin crear una clase serializer |
| `OpenApiParameter` | param query/path/header/cookie (o response header) | documentar un query/path param, o un header |
| `OpenApiResponse` | response + `description` + `examples` | describir una respuesta (éxito/error) por status |
| `OpenApiRequest` | request + `encoding` + `examples` | encoding a medida de `x-www-form-urlencoded`/`multipart/*` |
| `OpenApiExample` | valor de ejemplo para param/request/response | dar ejemplos concretos en Swagger/Redoc |
| `OpenApiWebhook` | documentar un **webhook** saliente (POST out-of-band que emite la API) | publicar el contrato de un webhook emitido |
| `OpenApiCallback` | documentar un **callback** que el receptor espera | pareja del webhook, desde la perspectiva del origen |
| `PolymorphicProxySerializer` | request/response polimórfico (varios serializers + discriminador) | un endpoint que devuelve tipos distintos según caso |

### `@extend_schema` — argumentos

| Argumento | Qué hace |
|---|---|
| `operation_id` | id único de la operación (si se fija a mano, no puede colisionar) |
| `parameters` | lista de `OpenApiParameter` (query/path/header/cookie) |
| `request` | serializer / `OpenApiTypes` / dict por media-type / `inline_serializer` para el body |
| `responses` | serializer / `OpenApiResponse` / dict `{status: …}` por respuesta |
| `auth` | override de esquemas de seguridad de la operación |
| `description` | descripción larga de la operación |
| `summary` | título corto de la operación |
| `deprecated` | marca la operación como obsoleta |
| `tags` | agrupación de la operación en la UI |
| `filters` | fuerza el prosesado de filtros aunque el heurístico lo omita |
| `exclude` | quita la operación del schema |
| `operation` | dict OpenAPI crudo (bypass total del introspector) |
| `methods` | HTTP methods a los que aplica el decorador (multi-método) |
| `versions` | scope de versión (con versioning de DRF activo) |
| `examples` | lista de `OpenApiExample` para la operación |
| `extensions` | campos `x-…` a nivel operación (p. ej. `x-code-samples`) |
| `callbacks` | lista de `OpenApiCallback` |
| `external_docs` | link a documentación externa de la operación |

## `drf_spectacular.types.OpenApiTypes`

Enum de tipos/formatos OpenAPI que se pasan a `OpenApiParameter(...)`, a `responses`
o a `@extend_schema_field`. Para tipos básicos, un hint de Python
(`str`/`int`/`bool`/`Decimal`/`datetime`/`UUID`) es equivalente.

| Grupo | Miembros |
|---|---|
| Texto | `STR`, `PASSWORD`, `EMAIL`, `IDN_EMAIL`, `HOSTNAME`, `IDN_HOSTNAME`, `URI`, `URI_REF`, `URI_TPL`, `IRI`, `IRI_REF`, `REGEX`, `JSON_PTR`, `JSON_PTR_REL` |
| Numérico | `INT`, `INT32`, `INT64`, `UINT32`, `UINT64`, `NUMBER`, `FLOAT`, `DOUBLE`, `DECIMAL` |
| Booleano | `BOOL` |
| Fecha/tiempo | `DATE`, `DATETIME`, `TIME`, `DURATION` |
| Binario | `BYTE` (base64), `BINARY` (bytes crudos) |
| Red | `IP4`, `IP6`, `MAC` |
| Identidad | `UUID` |
| Estructural | `OBJECT` (`dict`), `ANY` (`{}`), `NONE` (request/response vacío) |

Notas: `DECIMAL` se emite como `number/double`. `NONE` documenta un cuerpo
ausente (p. ej. un `204`/logout). `ANY` es el schema libre `{}`.

## `drf_spectacular.views`

| Vista | Qué sirve |
|---|---|
| `SpectacularAPIView` | el schema crudo (`/schema/`); negocia YAML/JSON; args `custom_settings=`, `api_version=`, `urlconf=` |
| `SpectacularSwaggerView` | UI Swagger |
| `SpectacularRedocView` | UI Redoc |
| `SpectacularSwaggerSplitView` | Swagger en dos requests (html + js separados) — variante CSP-friendly |
| `SpectacularJSONAPIView` | fuerza salida JSON del schema |
| `SpectacularYAMLAPIView` | fuerza salida YAML del schema |
| `SpectacularSwaggerOauthRedirectView` | endpoint de redirect del flujo OAuth2 en Swagger UI |

Las vistas de docs traen sus propias `authentication_classes`/`permission_classes`
(gobernadas por `SERVE_PUBLIC`/`SERVE_PERMISSIONS`/`SERVE_AUTHENTICATION`) y son la
superficie pública del schema (ver `backend-drf/references/schema.md`).

## `drf_spectacular.extensions` — las 5 clases base

Se subclasan para arreglar la introspección de piezas que el heurístico no cubre.
Registro automático vía `__init_subclass__` al importar el módulo que las define.
`priority` (default 0; built-in −1) — subir para ganar a una built-in.

| Clase base | Método(s) a implementar | Qué documenta |
|---|---|---|
| `OpenApiAuthenticationExtension` | `get_security_definition` (+ `get_security_requirement`) | un esquema de autenticación (target = la `authentication` class) |
| `OpenApiSerializerExtension` | `map_serializer` (+ `get_name`/`get_identity`) | la forma de un serializer no introspectable |
| `OpenApiSerializerFieldExtension` | `map_serializer_field` (+ `get_name`) | un serializer **field** custom |
| `OpenApiViewExtension` | `view_replacement` (+ `get_match`) | reemplaza una vista opaca por una introspectable |
| `OpenApiFilterExtension` | `get_schema_operation_parameters` | los parámetros de un filter backend |

Cada extensión declara su `target_class` (import path del objeto que arregla).
Detalle del patrón: `customization.md` (paso 5), `blueprints.md`.

## `drf_spectacular.hooks`

Funciones para las listas `PREPROCESSING_HOOKS` / `POSTPROCESSING_HOOKS`.

| Hook | Fase | Qué hace |
|---|---|---|
| `preprocess_exclude_path_format` | pre | quita las rutas duplicadas con sufijo `{format}` |
| `postprocess_schema_enums` | post | consolida enums con mismo nombre/choices en componentes reutilizables |
| `postprocess_schema_enum_id_removal` | post | limpia ids temporales usados para agrupar enums |

Un hook propio es una función `(result, generator, request, public) -> result`
en cualquiera de las dos listas.

## `drf_spectacular.openapi.AutoSchema` — subclasable

Es el `DEFAULT_SCHEMA_CLASS`. Se subclasa para un introspector global a medida y se
reasigna en `REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS']` (o por vista con
`schema = MyAutoSchema()`).

Métodos overridables frecuentes: `get_operation`, `get_operation_id`, `get_tags`,
`get_summary`, `get_description`, `get_request_serializer`,
`get_response_serializers`, `get_override_parameters`, `get_auth`, `is_excluded`,
`is_deprecated`, `map_serializer`, `map_field`, `resolve_serializer`.

`method_mapping` (HTTP → nombre de operación por default):
`get→retrieve`, `post→create`, `put→update`, `patch→partial_update`,
`delete→destroy`.

## `drf_spectacular.contrib`

Extensiones incluidas para librerías de terceros comunes. La más usada:

- `drf_spectacular.contrib.django_filters.DjangoFilterExtension` — documenta los
  `FilterSet` de **django-filter**; los filtros sub-especificados se afinan con
  `extend_schema_field` sobre el field/método del `FilterSet`.

`drf_spectacular.contrib` trae extensiones adicionales para otras librerías
(auth, polymorphic, etc.); se activan solo si su `target_class` está instalado.

## Referencias cruzadas

- `customization.md` — cómo se usan `@extend_schema`/extensiones/hooks.
- `openapi-types-and-yasg.md` — el detalle de `OpenApiTypes` y docstrings.
- `spectacular-settings.md` — hooks wired + registro de extensiones.
- `blueprints.md` — `AutoSchema` custom y extensiones de terceros.
- `faq-troubleshooting.md` — `SwaggerSplitView` (CSP), `swagger_fake_view`.
- `client-generation.md` — `COMPONENT_SPLIT_REQUEST` y validación del schema.
```
